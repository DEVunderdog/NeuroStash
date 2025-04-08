-- name: CreateKnowledgeBase :one
insert into knowledge_bases (
    user_id,
    name
) values (
    $1, $2
) returning *;

-- name: DeleteKnowledgeBase :exec
delete from knowledge_bases
where name = sqlc.arg(knowledge_base_name);
