-- name: CreateEmptyDocuments :many
insert into documents_registry (
    user_id,
    file_name,
    object_key,
    lock_status,
    op_status
) select @user_id::int,
       unnest(@file_names::varchar[]), 
       unnest(@object_keys::varchar[]),
       @lock_status::bool,
       @op_status::operation_status
returning id, file_name, updated_at;

-- name: ListConflictingFiles :many
select id, file_name, object_key from documents_registry
where ((lock_status = sqlc.arg(first_lock_condition) AND op_status = sqlc.arg(first_op_status)) OR
    (lock_status = sqlc.arg(second_lock_condition) AND op_status = sqlc.arg(second_op_status)) OR
    (lock_status = sqlc.arg(third_lock_condition) AND op_status = sqlc.arg(third_op_status)) OR
    (lock_status = sqlc.arg(fourth_lock_condition) AND op_status = sqlc.arg(fourth_op_status)) OR
    (lock_status = sqlc.arg(fifth_lock_condition) AND op_status = sqlc.arg(fifth_op_status)))
    AND
    user_id = sqlc.arg(user_id);

-- name: GetFilesObjectKeys :many
select object_key from documents_registry 
    where user_id = sqlc.arg(user_id) and file_name = any(@filenames::string[]);

-- name: UpdateDocumentUploadStatus :execresult
update documents_registry
set
    lock_status = sqlc.arg(lock_status),
    op_status = sqlc.arg(op_status),
    updated_at = now()
where id = any(@ids::int[]) and lock_status = sqlc.arg(current_lock_status) and updated_at = sqlc.arg(updated_at);

-- name: SyncUpdateDocument :execresult
update documents_registry
set
    lock_status = sqlc.arg(lock_status),
    op_status = sqlc.arg(op_status),
    updated_at = now()
where id = any(@ids::int[]);


-- name: DeleteFiles :execresult
delete from documents_registry
where id = any(@ids::int[]) and lock_status = sqlc.arg(current_lock_status) and updated_at = sqlc.arg(updated_at);

-- name: SyncDelete :execresult
delete from documents_registry
where id = any(@ids::int[]);

