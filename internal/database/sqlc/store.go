package database

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Store interface {
	Querier
	RegisterUserTx(ctx context.Context, arg RegisterUserTxParams) error
	FileStatusTx(ctx context.Context, arg FileStatusTxParams) error
	SyncTx(ctx context.Context, recordThatExists, recordsNeedsToBeDelete []int32) error
}

type SQLStore struct {
	connPool *pgxpool.Pool
	*Queries
}

func NewStore(connPool *pgxpool.Pool) Store {
	return &SQLStore{
		connPool: connPool,
		Queries:  New(connPool),
	}
}
