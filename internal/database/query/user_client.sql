-- name: RegisterUser :one
insert into user_clients (
    email
) values (
    $1
) returning *;

