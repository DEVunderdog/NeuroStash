create table
    "encryption_keys" (
        id serial primary key,
        public_key text not null,
        private_key bytea not null,
        is_active boolean default false,
        created_at timestamptz default current_timestamp,
        updated_at timestamptz default current_timestamp
    );

create table
    "user_clients" (
        id serial primary key,
        email varchar(255) not null,
        created_at timestamptz default current_timestamp,
        updated_at timestamptz default current_timestamp
    );

create table
    "api_keys" (
        id serial primary key,
        user_id int not null,
        credential bytea not null,
        signature bytea not null,
        created_at timestamptz default current_timestamp,
        updated_at timestamptz default current_timestamp
    );

create type operation_status as enum ('PENDING', 'SUCCESS', 'FAILED');

create table
    "documents_registry" (
        id serial primary key,
        user_id int not null,
        file_name varchar(100) not null,
        object_key varchar(150) not null,
        lock_status bool not null,
        op_status operation_status not null default 'PENDING',
        created_at timestamptz default current_timestamp,
        updated_at timestamptz default current_timestamp
    );

alter table "api_keys" add constraint "fk_user_api_keys" foreign key ("user_id") references "user_clients" ("id") on update cascade on delete restrict;

alter table "documents_registry" add constraint "fk_user_documents_registry" foreign key ("user_id") references "user_clients" ("id") on update cascade on delete restrict;

create unique index idx_unique_filename on "documents_registry" ("file_name", "user_id");

create unique index idx_email on "user_clients" ("email");

create index idx_encryption_keys_active on "encryption_keys" ("is_active");

create index idx_file_registry_user_id on "documents_registry" ("user_id", "lock_status", "op_status");

create index idx_api_keys on "api_keys" ("credential");