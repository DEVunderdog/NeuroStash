create table
    "knowledge_bases" (
        id serial primary key,
        user_id int not null,
        name varchar(100) not null,
        created_at timestamptz default current_timestamp,
        updated_at timestamptz default current_timestamp
    );

create table
    "knowledge_base_documents" (
        id serial primary key,
        ingestion_id int not null,
        knowledge_base_id int not null,
        document_id int not null,
        created_at timestamptz default current_timestamp,
        updated_at timestamptz default current_timestamp
    );

create table
    "ingestion_jobs" (
        id serial primary key,
        resource_id uuid not null,
        op_status operation_status not null default 'PENDING',
        created_at timestamptz default current_timestamp,
        updated_at timestamptz default current_timestamp
    );

alter table knowledge_bases add constraint "fk_user_kb" foreign key ("user_id") references "user_clients" ("id") on update cascade on delete restrict;

alter table knowledge_base_documents add constraint "fk_kb" foreign key ("knowledge_base_id") references "knowledge_bases" ("id") on update cascade on delete cascade;

alter table knowledge_base_documents add constraint "fk_doc" foreign key ("document_id") references "documents_registry" ("id") on update cascade on delete cascade;

alter table knowledge_base_documents add constraint "fk_job" foreign key ("ingestion_id") references "ingestion_jobs" ("id") on update cascade on delete restrict;

create unique index idx_unique_kb_name on "knowledge_bases" ("user_id", "name");

create unique index idx_unique_kb_doc_combination on "knowledge_base_documents" ("knowledge_base_id", "document_id");

create index idx_job_status on "ingestion_jobs" ("resource_id", "op_status");