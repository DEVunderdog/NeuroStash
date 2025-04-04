drop index idx_encryption_keys_active;

drop index idx_unique_filename;

create index idx_encryption_keys_active on "encryption_keys" ("is_active");

create unique index idx_unique_filename on "documents_registry" ("file_name", "user_id");