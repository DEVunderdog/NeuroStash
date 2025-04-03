drop index idx_encryption_keys_active;

drop index idx_unique_filename;

-- cannot do this because the public key and private_key are very large hence exceeding the limit of leaf nodes to store
-- create index idx_encryption_keys_active on "encryption_keys" ("id")
--     include (public_key, private_key)
--     where is_active = true;

create index idx_encryption_keys_active on "encryption_keys" ("id") where is_active = true;

create unique index idx_unique_filename on "documents_registry" ("user_id", "file_name");
