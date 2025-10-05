-- Création de la base de données (exécuter en premier)
-- CREATE DATABASE pmc_bioscience;

-- Table des publications
CREATE TABLE IF NOT EXISTS publications (
    id SERIAL PRIMARY KEY,
    pmc_id VARCHAR(50) UNIQUE NOT NULL,
    pmid VARCHAR(50),
    doi VARCHAR(255),
    title TEXT NOT NULL,
    abstract TEXT,
    journal VARCHAR(500),
    publication_date VARCHAR(50),
    authors JSONB,
    keywords JSONB,
    hypothesis TEXT,
    key_findings JSONB,
    organisms_studied JSONB,
    space_conditions JSONB,
    full_text TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index pour recherches rapides
CREATE INDEX idx_pmc_id ON publications(pmc_id);
CREATE INDEX idx_pmid ON publications(pmid);
CREATE INDEX idx_doi ON publications(doi);
CREATE INDEX idx_publication_date ON publications(publication_date);
CREATE INDEX idx_title_search ON publications USING gin(to_tsvector('english', title));
CREATE INDEX idx_abstract_search ON publications USING gin(to_tsvector('english', abstract));
CREATE INDEX idx_keywords ON publications USING gin(keywords);

-- Table des erreurs de traitement
CREATE TABLE IF NOT EXISTS processing_errors (
    id SERIAL PRIMARY KEY,
    pmc_id VARCHAR(50),
    error_message TEXT,
    error_type VARCHAR(100),
    timestamp TIMESTAMP DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_error_pmc_id ON processing_errors(pmc_id);
CREATE INDEX idx_error_timestamp ON processing_errors(timestamp);

-- Table pour tracking des processus
CREATE TABLE IF NOT EXISTS processing_status (
    id SERIAL PRIMARY KEY,
    pmc_id VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    attempts INT DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_status ON processing_status(status);

-- Vue pour statistiques
CREATE OR REPLACE VIEW processing_stats AS
SELECT 
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    COUNT(*) FILTER (WHERE status = 'processing') as processing,
    COUNT(*) FILTER (WHERE status = 'pending') as pending,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (WHERE status = 'completed') as avg_processing_time_seconds
FROM processing_status;

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_publications_updated_at
    BEFORE UPDATE ON publications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();