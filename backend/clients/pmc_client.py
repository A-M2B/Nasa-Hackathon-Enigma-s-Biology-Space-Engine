import aiohttp
import asyncio
import xml.etree.ElementTree as ET
from typing import Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import re

class PMCAPIClient:
    """
    Client pour l'API officielle de PubMed Central
    """
    
    def __init__(self, email: str, api_key: Optional[str] = None):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.email = email
        self.api_key = api_key
        
        # Rate limiting : 3 req/sec sans clé, 10 req/sec avec clé
        self.rate_limit = 10 if api_key else 3
        self.semaphore = asyncio.Semaphore(self.rate_limit)
        
        # Session réutilisable
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.session:
                await self.session.close()

        async def close(self):
            """Ferme explicitement la session aiohttp"""
            if self.session and not self.session.closed:
                await self.session.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def fetch_article(self, pmc_id: str) -> Dict:
        """
        Récupère un article via l'API
        
        Args:
            pmc_id: "PMC11930778" ou "11930778"
        
        Returns:
            Article complet au format structuré
        """
        # Normalise PMC ID
        if not pmc_id.startswith('PMC'):
            pmc_id = f"PMC{pmc_id}"
        
        async with self.semaphore:  # Rate limiting
            # Récupère l'article au format XML
            xml_content = await self._fetch_full_text_xml(pmc_id)
            
            # Parse le XML
            article_data = self._parse_pmc_xml(xml_content, pmc_id)
            
            return article_data
    
    async def _fetch_full_text_xml(self, pmc_id: str) -> str:
        """
        Récupère le XML complet de l'article
        """
        # Enlève le préfixe PMC pour l'API
        numeric_id = pmc_id.replace('PMC', '')
        
        params = {
            'db': 'pmc',
            'id': numeric_id,
            'retmode': 'xml',
            'email': self.email
        }
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        url = f"{self.base_url}/efetch.fcgi"
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"API error {response.status}: {error_text}")
            
            return await response.text()
    
    def _parse_pmc_xml(self, xml_content: str, pmc_id: str) -> Dict:
        """
        Parse le XML PMC en structure Python (format JATS)
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise Exception(f"Erreur de parsing XML pour {pmc_id}: {e}")
        
        article = {'pmc_id': pmc_id}
        
        # 1. MÉTADONNÉES
        front = root.find('.//front')
        if front is not None:
            article['metadata'] = self._parse_metadata(front, pmc_id)
        else:
            article['metadata'] = {'pmc_id': pmc_id}
        
        # 2. CORPS DE L'ARTICLE
        body = root.find('.//body')
        if body is not None:
            article['sections'] = self._parse_body_sections(body)
        else:
            article['sections'] = {}
        
        # 3. RÉFÉRENCES
        back = root.find('.//back')
        if back is not None:
            article['references'] = self._parse_references(back)
        else:
            article['references'] = []
        
        # 4. FIGURES et TABLES
        article['figures'] = self._parse_figures(root, pmc_id)
        article['tables'] = self._parse_tables(root)
        
        # 5. TEXTE COMPLET
        article['full_text'] = self._extract_full_text(article)
        
        return article
    
    def _parse_metadata(self, front, pmc_id: str) -> Dict:
        """Parse les métadonnées"""
        metadata = {'pmc_id': pmc_id}
        
        # Titre
        title = front.find('.//article-title')
        if title is not None:
            metadata['title'] = self._get_element_text(title)
        
        # Auteurs
        authors = []
        for contrib in front.findall('.//contrib[@contrib-type="author"]'):
            author = {}
            surname = contrib.find('.//surname')
            given_names = contrib.find('.//given-names')
            
            if surname is not None:
                author['last_name'] = surname.text or ""
            if given_names is not None:
                author['first_name'] = given_names.text or ""
            
            if author:
                authors.append(author)
        
        metadata['authors'] = authors
        
        # Affiliations
        affiliations = {}
        for aff in front.findall('.//aff'):
            aff_id = aff.get('id', 'default')
            aff_text = self._get_element_text(aff)
            affiliations[aff_id] = aff_text
        
        metadata['affiliations'] = affiliations
        
        # Journal
        journal_title = front.find('.//journal-title')
        if journal_title is not None:
            metadata['journal'] = journal_title.text
        
        # Date
        pub_date = front.find('.//pub-date[@pub-type="epub"]')
        if pub_date is None:
            pub_date = front.find('.//pub-date')
        
        if pub_date is not None:
            year = pub_date.find('.//year')
            month = pub_date.find('.//month')
            day = pub_date.find('.//day')
            
            date_parts = []
            if year is not None and year.text:
                date_parts.append(year.text)
            if month is not None and month.text:
                date_parts.append(month.text.zfill(2))
            if day is not None and day.text:
                date_parts.append(day.text.zfill(2))
            
            metadata['publication_date'] = '-'.join(date_parts) if date_parts else None
        
        # DOI
        article_id_doi = front.find('.//article-id[@pub-id-type="doi"]')
        if article_id_doi is not None:
            metadata['doi'] = article_id_doi.text
        
        # PMID
        article_id_pmid = front.find('.//article-id[@pub-id-type="pmid"]')
        if article_id_pmid is not None:
            metadata['pmid'] = article_id_pmid.text
        
        # Abstract
        abstract = front.find('.//abstract')
        if abstract is not None:
            metadata['abstract'] = self._get_element_text(abstract)
        
        # Keywords
        keywords = []
        for kwd in front.findall('.//kwd'):
            if kwd.text:
                keywords.append(kwd.text)
        metadata['keywords'] = keywords
        
        return metadata
    
    def _parse_body_sections(self, body) -> Dict[str, str]:
        """Parse les sections du corps"""
        sections = {}
        
        for sec in body.findall('.//sec'):
            title_elem = sec.find('.//title')
            if title_elem is not None and title_elem.text:
                section_title = title_elem.text.lower().strip()
                
                # Normalise les titres
                key = self._normalize_section_title(section_title)
                
                # Extrait le texte
                section_text = self._get_element_text(sec)
                
                # Combine si section déjà existe
                if key in sections:
                    sections[key] += '\n\n' + section_text
                else:
                    sections[key] = section_text
        
        return sections
    
    def _normalize_section_title(self, title: str) -> str:
        """Normalise les titres de sections"""
        title_lower = title.lower()
        
        if 'introduction' in title_lower or 'background' in title_lower:
            return 'introduction'
        elif 'method' in title_lower or 'material' in title_lower:
            return 'methods'
        elif 'result' in title_lower:
            return 'results'
        elif 'discussion' in title_lower:
            return 'discussion'
        elif 'conclusion' in title_lower:
            return 'conclusion'
        else:
            return title_lower.replace(' ', '_')
    
    def _parse_references(self, back) -> list:
        """Parse les références"""
        references = []
        
        ref_list = back.find('.//ref-list')
        if ref_list is not None:
            for ref in ref_list.findall('.//ref'):
                ref_data = {'id': ref.get('id', '')}
                
                mixed_citation = ref.find('.//mixed-citation')
                if mixed_citation is not None:
                    ref_data['citation'] = self._get_element_text(mixed_citation)
                
                pmid = ref.find('.//pub-id[@pub-id-type="pmid"]')
                if pmid is not None:
                    ref_data['pmid'] = pmid.text
                
                doi = ref.find('.//pub-id[@pub-id-type="doi"]')
                if doi is not None:
                    ref_data['doi'] = doi.text
                
                references.append(ref_data)
        
        return references
    
    def _parse_figures(self, root, pmc_id: str) -> list:
        """Parse les figures"""
        figures = []
        
        for fig in root.findall('.//fig'):
            figure_data = {'id': fig.get('id', '')}
            
            label = fig.find('.//label')
            if label is not None:
                figure_data['label'] = label.text
            
            caption = fig.find('.//caption')
            if caption is not None:
                title = caption.find('.//title')
                if title is not None:
                    figure_data['title'] = title.text
                
                figure_data['caption'] = self._get_element_text(caption)
            
            graphic = fig.find('.//graphic')
            if graphic is not None:
                href = graphic.get('{http://www.w3.org/1999/xlink}href')
                if href:
                    figure_data['image_url'] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/bin/{href}"
            
            figures.append(figure_data)
        
        return figures
    
    def _parse_tables(self, root) -> list:
        """Parse les tableaux"""
        tables = []
        
        for table_wrap in root.findall('.//table-wrap'):
            table_data = {'id': table_wrap.get('id', '')}
            
            label = table_wrap.find('.//label')
            if label is not None:
                table_data['label'] = label.text
            
            caption = table_wrap.find('.//caption')
            if caption is not None:
                table_data['caption'] = self._get_element_text(caption)
            
            table = table_wrap.find('.//table')
            if table is not None:
                table_data['data'] = self._parse_xml_table(table)
            
            tables.append(table_data)
        
        return tables
    
    def _parse_xml_table(self, table) -> Dict:
        """Parse une table XML"""
        headers = []
        rows = []
        
        thead = table.find('.//thead')
        if thead is not None:
            for tr in thead.findall('.//tr'):
                header_row = []
                for th in tr.findall('.//th'):
                    header_row.append(self._get_element_text(th))
                if header_row:
                    headers = header_row
        
        tbody = table.find('.//tbody')
        if tbody is not None:
            for tr in tbody.findall('.//tr'):
                row = []
                for td in tr.findall('.//td'):
                    row.append(self._get_element_text(td))
                if row:
                    rows.append(row)
        
        return {'headers': headers, 'rows': rows}
    
    def _extract_full_text(self, article: Dict) -> str:
        """Combine abstract et sections en texte complet"""
        parts = []
        
        # Abstract
        abstract = article.get('metadata', {}).get('abstract', '')
        if abstract:
            parts.append(f"ABSTRACT\n{abstract}")
        
        # Sections dans l'ordre
        sections = article.get('sections', {})
        section_order = ['introduction', 'methods', 'results', 'discussion', 'conclusion']
        
        for section_name in section_order:
            if section_name in sections:
                parts.append(f"{section_name.upper()}\n{sections[section_name]}")
        
        # Autres sections
        for key, text in sections.items():
            if key not in section_order:
                parts.append(f"{key.upper()}\n{text}")
        
        return '\n\n'.join(parts)
    
    def _get_element_text(self, element) -> str:
        """Extrait le texte d'un élément XML"""
        if element is None:
            return ""
        
        # Récupère tout le texte, y compris des sous-éléments
        text_parts = []
        for text in element.itertext():
            clean_text = text.strip()
            if clean_text:
                text_parts.append(clean_text)
        
        return ' '.join(text_parts)
    
if __name__ == "__name__":
    id = "PMC4136787"