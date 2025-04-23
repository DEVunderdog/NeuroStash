-- name: CreateKnowledgeBase :one
insert into knowledge_bases (
    user_id,
    name
) values (
    $1, $2
) returning *;

-- name: ListUserKnowledgeBases :many
select id, name from knowledge_bases where user_id = sqlc.arg(user_id);

-- name: DeleteKnowledgeBase :exec
delete from knowledge_bases
where id = sqlc.arg(knowledge_base_id) and user_id = sqlc.arg(user_id);
