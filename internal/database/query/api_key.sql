-- name: CreateApiKey :one
insert into api_keys (
    user_id,
    credential,
    signature
) values (
    $1, $2, $3
) returning *;

-- name: GetApiKeyPayload :one
select user_id, signature from api_keys
where credential = sqlc.arg('credential');

-- name: ListApiKeys :many
select credential from api_keys
where user_id = sqlc.arg('user_id');

-- name: DeleteApiKey :execresult
delete from api_keys
where credential = sqlc.arg(credential) and user_id = sqlc.arg(user_id);