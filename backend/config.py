import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

class PMCConfig(BaseModel):
    email: str = Field(default_factory=lambda: os.getenv('NCBI_EMAIL'))
    api_key: str = Field(default_factory=lambda: os.getenv('NCBI_API_KEY'))

class AIConfig(BaseModel):
    groq_api_key: str = Field(default_factory=lambda: os.getenv('GROQ_API_KEY'))
    embedding_model: str = Field(default_factory=lambda: os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'))

class PostgresConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv('POSTGRES_HOST', 'localhost'))
    port: int = Field(default_factory=lambda: int(os.getenv('POSTGRES_PORT', 5432)))
    user: str = Field(default_factory=lambda: os.getenv('POSTGRES_USER', 'postgres'))
    password: str = Field(default_factory=lambda: os.getenv('POSTGRES_PASSWORD'))
    database: str = Field(default_factory=lambda: os.getenv('POSTGRES_DB', 'pmc_bioscience'))

class Neo4jConfig(BaseModel):
    uri: str = Field(default_factory=lambda: os.getenv('NEO4J_URI'))
    user: str = Field(default_factory=lambda: os.getenv('NEO4J_USER', 'neo4j'))
    password: str = Field(default_factory=lambda: os.getenv('NEO4J_PASSWORD'))

class ElasticsearchConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv('ELASTICSEARCH_HOST', 'localhost'))
    port: int = Field(default_factory=lambda: int(os.getenv('ELASTICSEARCH_PORT', 9200)))
    
    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

class WeaviateConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv('WEAVIATE_HOST', 'localhost'))
    port: int = Field(default_factory=lambda: int(os.getenv('WEAVIATE_PORT', 8080)))
    grpc_port: int = Field(default_factory=lambda: int(os.getenv('WEAVIATE_GRPC_PORT', 50051)))
    scheme: str = Field(default_factory=lambda: os.getenv('WEAVIATE_SCHEME', 'http'))
    
    @property
    def url(self):
        return f"{self.scheme}://{self.host}:{self.port}"

class Config:
    pmc = PMCConfig()
    ai = AIConfig()
    postgres = PostgresConfig()
    neo4j = Neo4jConfig()
    elasticsearch = ElasticsearchConfig()
    weaviate = WeaviateConfig()

config = Config()