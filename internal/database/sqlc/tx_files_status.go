package database

import (
	"context"
	"errors"

	"github.com/DEVunderdog/neurostash/internal/types"
	"github.com/jackc/pgx/v5/pgtype"
)

type FileStatusTxParams struct {
	FilesToBeDeleted  []int32
	FilesToBeUnlocked []int32
	UpdatedAt         pgtype.Timestamptz
}

func (store *SQLStore) FileStatusTx(
	ctx context.Context,
	args FileStatusTxParams,
) error {
	return store.execTx(ctx, func(q *Queries) error {
		if len(args.FilesToBeDeleted) == 0 && len(args.FilesToBeUnlocked) == 0 {
			return errors.New("please provide files to be deleted or unlocked")
		}

		if len(args.FilesToBeUnlocked) != 0 {
			result, err := q.UpdateDocumentUploadStatus(ctx, UpdateDocumentUploadStatusParams{
				LockStatus:        types.Unlocked,
				OpStatus:          OperationStatusSUCCESS,
				Ids:               args.FilesToBeUnlocked,
				CurrentLockStatus: types.Locked,
				UpdatedAt:         args.UpdatedAt,
			})
			if err != nil {
				return err
			}

			if result.RowsAffected() == 0 {
				return errors.New("zero rows affected while updating document status")
			}
		}

		if len(args.FilesToBeDeleted) != 0 {
			result, err := q.DeleteFiles(ctx, DeleteFilesParams{
				Ids:               args.FilesToBeDeleted,
				CurrentLockStatus: types.Locked,
				UpdatedAt:         args.UpdatedAt,
			})
			if err != nil {
				return err
			}

			if result.RowsAffected() == 0 {
				return errors.New("zero rows affected while deleting files")
			}
		}

		return nil
	})
}

func (store *SQLStore) SyncTx(
	ctx context.Context,
	recordThatExists, recordsNeedsToBeDelete []int32,
) error {
	return store.execTx(ctx, func(q *Queries) error {
		if len(recordThatExists) == 0 && len(recordsNeedsToBeDelete) == 0 {
			return errors.New("please provide records to sync")
		}

		if len(recordThatExists) != 0 {
			result, err := q.SyncUpdateDocument(ctx, SyncUpdateDocumentParams{
				LockStatus: types.Unlocked,
				OpStatus:   OperationStatusSUCCESS,
				Ids:        recordThatExists,
			})

			if err != nil {
				return err
			}

			if result.RowsAffected() == 0 {
				return errors.New("zero rows affected while sync update")
			}
		}

		if len(recordsNeedsToBeDelete) != 0 {
			result, err := q.SyncDelete(ctx, recordsNeedsToBeDelete)
			if err != nil {
				return err
			}

			if result.RowsAffected() == 0 {
				return errors.New("zero rows affected while sync delete")
			}
		}

		return nil
	})
}
