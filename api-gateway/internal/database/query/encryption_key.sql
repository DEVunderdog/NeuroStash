-- name: CreateEncryptionKeys :one
insert into encryption_keys (
    public_key,
    private_key,
    is_active
) values (
    $1, $2, $3
) returning *;

-- name: GetActiveKey :one
select id, public_key, private_key, created_at from encryption_keys
    where is_active = 'true';

-- name: CountEncryptionKeys :one
select count(*) from encryption_keys;

-- name: DeleteEncryptionKey :execresult
delete from encryption_keys where id = sqlc.arg(id);