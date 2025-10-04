# NeuroStash

## Design Videos
- Please go through the videos I have explain the design problems that I have tried to solve, what I though while solving those problems.  
   - [Parent Document Retriever](https://www.youtube.com/watch?v=YlVMd3XD5V8)  
   - [File Management](https://www.youtube.com/watch?v=cJP3_MdRJ8s)  
   - [User Management](https://www.youtube.com/watch?v=iUO-YAGVFco)  
   - [Milvus and Knowledge base](https://www.youtube.com/watch?v=GP2KpScLB38)  

## Introduction
NeuroStash is an intelligent document management system that powers Large Language Models (LLMs) operations by providing document processing and semantic search capabilities. It's specifically designed for small to medium enterprises seeking a cost-effective, self-hosted alternative to expensive enterprise solutions.

### Key Features
- Document processing and semantic search
- Secure document storage and management
- API-first architecture for easy integration
- Scalable vector search capabilities

### Cost-Effective Design
NeuroStash is built with cost optimization in mind:

1. **Self-Hosted Infrastructure**
   - Control over computing resources

2. **Efficient Resource Usage**
   - OpenAI's embeddings API for cost-effective document processing
   - Optimized storage utilization
   - Efficient vector search implementation

3. **AWS Free Tier Compatible**
   - Leverages AWS free tier services
   - S3 for document storage
   - SQS for reliable async processing
   - Minimal operational costs for small deployments

## API Documentation
Once the application is running, you can access the interactive API documentation through:

- **Swagger UI**: Visit `http://localhost:8000/docs` for an interactive API documentation with a testing interface
- **ReDoc**: Visit `http://localhost:8000/redoc` for a more detailed, readable API documentation
- whatever port or domain you set it shouldn't be fixed I have just passed as reference.

These documentation endpoints provide:
- Complete API endpoint listing
- Request/response schemas
- Authentication requirements
- Interactive testing capabilities (Swagger UI only)

## NeuroStash Local Setup Guide

###  Application Environment Setup

####  Notes:
- The docker environment file (`docker/.env`) manages container-specific configurations
- The application environment file (`.env` in root directory) contains application-specific settings
- When running with Docker Compose, both files are needed:
  - Docker Compose uses `docker/.env` for container setup
  - The application container uses the root `.env` file for application configuration

The application requires the following environment variables to be set. Copy `.env.example` to `.env` and configure these variables:

```sh
POSTGRES_SERVER=localhost      # PostgreSQL server hostname
POSTGRES_PORT=5432            # PostgreSQL port
POSTGRES_USER=root            # Database username
POSTGRES_PASSWORD=root        # Database password 
POSTGRES_DB=db_name          # Database name

PROJECT_NAME=NeuroStash      # Application name

AWS_REGION=us-east-1         # AWS region for services
AWS_KMS_KEY_ID=             # KMS key ID for encryption (production only)
AWS_ACCESS_KEY_ID=          # AWS access key ID
AWS_SECRET_ACCESS_KEY=      # AWS secret access key
AWS_BUCKET_NAME=            # S3 bucket name for file storage
AWS_PRESIGNED_URL_EXP=3600  # Expiry time in seconds for presigned URLs
AWS_QUEUE_URL=              # SQS queue URL

JWT_ACCESS_TOKEN_HOURS=24    # JWT token validity in hours
JWT_ISSUER=                 # JWT issuer name
JWT_AUDIENCE=               # JWT audience name

SMTP_HOST=smtp.gmail.com    # SMTP server hostname
SMTP_USER=                 # SMTP username
SMTP_PASSWORD=             # SMTP password
EMAILS_FROM_EMAIL=         # Sender email address
EMAILS_FROM_NAME=          # Sender name
FIRST_ADMIN=               # Admin email to receive initial API key

OPENAI_KEY=                # OpenAI API key for embeddings
MILVUS_URL=               # Milvus server URL
MILVUS_DATABASE=          # Milvus database name
```
#### Admin User
- Please provide `FIRST_ADMIN` email to receive top-level API Key which has all priveleges in the application

#### Development vs Production
- For development, set `ENVIRONMENT=dev` (default)
- For production, set `ENVIRONMENT=prod`
  - In production, AWS KMS key is required for key encryption
  - In development, local encryption is used instead

#### Optional Variables
- `MILVUS_USER` - Milvus username (if authentication is enabled)
- `MILVUS_PASSWORD` - Milvus password (if authentication is enabled)
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are required only in development
  - Production should use IAM roles instead if deployed on AWS

### Docker Environment Setup

```sh
# PostgreSQL Configuration
POSTGRES_USER=db_user        # Default database user
POSTGRES_PASSWORD=db_password # Default database password
POSTGRES_DB=neurostash      # Default database name
POSTGRES_PORT=5432          # Host port mapping for PostgreSQL

# Milvus Configuration
MILVUS_PORT=19530          # Host port mapping for Milvus
MILVUS_METRICS_PORT=9091   # Host port mapping for Milvus metrics

# MinIO Configuration
MINIO_ROOT_USER=minioadmin     # MinIO root user
MINIO_ROOT_PASSWORD=minioadmin # MinIO root password
MINIO_CONSOLE_PORT=9001       # Host port mapping for MinIO console
MINIO_API_PORT=9000          # Host port mapping for MinIO API

# Application Configuration
APP_PORT=8000              # Host port mapping for the application
```

### How to run the project
> ⚠️ **Note**  
> The `docker/` contains docker compose file that helps running application locally and in production.  

- You can find `Makefile` at the root of the project for the commands
- Please run the commands from root directory
    - When running for first time
        - enter the command `make build` will first then subsequent because to build the image
    - if containers are already build then run
        - `make run` will run the microservice containers and application would start
        - `make stop` will stop the application
        - `make logs SERVICE=name` you can inspect logs of running container service names to inspect are  
           `etcd`, `minio`, `standalone`, `postgres`, `app-server`

## Technology Stack & Dependencies

### Core Technologies

#### FastAPI
- **Purpose**: Modern, high-performance web framework for building APIs
- **Why**: 
  - Automatic API documentation generation
  - Built-in data validation via Pydantic
  - Asynchronous support for handling concurrent requests
  - Type hints and modern Python features
  - High performance compared to traditional frameworks

#### PostgreSQL
- **Purpose**: Primary relational database
- **Why**:
  - I just love it

#### Milvus
- **Purpose**: Vector database for semantic search
- **Why**:
  - Optimized for high-dimensional vector similarity search
  - Scalable architecture for large document collections
  - Support for hybrid searches (vector + scalar filtering)
  - Production-ready with clustering capabilities
  - Active development and community support
  - Completely OpenSource can be self-hosted


### Key Dependencies

#### Language Processing Stack
- **LangChain (v0.3.26)**
  - Parsing various documents type
  - Semantic Chunking
  - OpenAI asynchronous embeddings  
    calculations for semantic chunking

- **Spacy (v3.8.7)**
  - for splitting individual sentences from  
    large chunks

- **OpenAI Integration (v1.97.1)**
  - Provides high-quality embeddings
  - using text-embeddings-3-large (3072 Dimension)

#### API & Security
- **Pydantic (v2.11.4)**
  - Type validation and settings management
  - API schema generation
  - Integration with FastAPI
  - Runtime type checking

- **SQLAlchemy (v2.0.40) and Alembic (v1.15.2)**
  - Type-safe database operations
  - Database agnostic ORM
  - Connection pooling
  - Migration support via Alembic

- **Python-Jose (v3.4.0)**
  - JWT token handling for authentication
  - Active maintenance and security updates

#### AWS Integration
- **Boto3 (v1.38.16)**
  - Official AWS SDK
  - S3 for Object Management
  - SQS Queue for Asynchronous processings


### System Requirements
- Python 3.12+
- Docker Engine 24.0+
- Docker Compose v2.0+
- 4GB RAM minimum (8GB recommended)
- 20GB disk space

For complete dependency specifications, refer to `requirements.txt`.
