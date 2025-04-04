package server

import (
	"context"

	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"github.com/DEVunderdog/neurostash/internal/types"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"
)

func (server *Server) Sync(ctx context.Context, req *emptypb.Empty) (*pb.Response, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	conflictedFiles, err := server.store.ListConflictingFiles(ctx, database.ListConflictingFilesParams{
		FirstLockCondition:  types.Locked,
		FirstOpStatus:       database.OperationStatusPENDING,
		SecondLockCondition: types.Locked,
		SecondOpStatus:      database.OperationStatusFAILED,
		ThirdLockCondition:  types.Locked,
		ThirdOpStatus:       database.OperationStatusSUCCESS,
		FourthLockCondition: types.Unlocked,
		FourthOpStatus:      database.OperationStatusFAILED,
		FifthLockCondition:  types.Unlocked,
		FifthOpStatus:       database.OperationStatusPENDING,
		UserID:              authPayload.UserId,
	})
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error listing conflicted files: %s", err.Error())
	}

	if len(conflictedFiles) == 0 {
		return &pb.Response{
			Message: "none conflicted files found",
		}, nil
	}

	recordsThatExists := make([]int32, 0, len(conflictedFiles))
	recordNeedsToDelete := make([]int32, 0, len(conflictedFiles))

	for _, item := range conflictedFiles {
		exists, err := server.awsClient.ObjectExists(ctx, item.ObjectKey)
		if err != nil {
			return nil, status.Errorf(codes.Internal, "error listing object keys: %s", err.Error())
		}

		if exists {
			recordsThatExists = append(recordsThatExists, item.ID)
		} else {
			recordNeedsToDelete = append(recordNeedsToDelete, item.ID)
		}
	}

	err = server.store.SyncTx(ctx, recordsThatExists, recordNeedsToDelete)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error syncing in database")
	}

	return &pb.Response{
		Message: "successfully sync up",
	}, nil
}
