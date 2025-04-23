package server

import (
	"context"
	"encoding/json"

	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"github.com/DEVunderdog/neurostash/internal/queue"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func (server *Server) IngestData(
	ctx context.Context,
	req *pb.IngestDataRequest,
) (*pb.IngestDataResponse, error) {
	payload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	files := req.GetFiles()
	if len(files) == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "bad request body please provide files")
	}

	knowledgeBaseID := req.GetKnowledgeBaseId()
	if knowledgeBaseID == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "bad request body please provide knowledge base id")
	}

	objectKeysWithIDs, err := server.store.GetFilesObjectKeysWithID(ctx, database.GetFilesObjectKeysWithIDParams{
		UserID:    payload.UserId,
		Filenames: files,
	})
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error fetching files object key: %s", err.Error())
	}

	resourceID, err := uuid.NewV7()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error generating unique resource v7 id: %s", err.Error())
	}

	ingestionJob, err := server.store.CreateIngestionJob(ctx, database.CreateIngestionJobParams{
		ResourceID: pgtype.UUID{
			Bytes: resourceID,
			Valid: true,
		},
		OpStatus: database.OperationStatusPENDING,
	})
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error creating ingestion job in database: %s", err.Error())
	}

	messageFiles := make([]queue.ObjectKeysWithIDs, 0, len(objectKeysWithIDs))

	for _, item := range objectKeysWithIDs {
		objectKeyWithID := queue.ObjectKeysWithIDs{
			ID:        item.ID,
			ObjectKey: item.ObjectKey,
		}
		messageFiles = append(messageFiles, objectKeyWithID)
	}

	sendMessage := queue.SendMessageStructure{
		IngestionJobID: ingestionJob.ResourceID.String(),
		Files:          messageFiles,
	}

	jsonData, err := json.Marshal(sendMessage)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error marshalling json data: %s", err.Error())
	}

	err = server.queueClient.Push(jsonData)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error pushing message to queue: %s", err.Error())
	}

	return &pb.IngestDataResponse{
		JobResourceId: ingestionJob.ResourceID.String(),
	}, nil
}

func (server *Server) IngestDataStatus(
	ctx context.Context,
	req *pb.IngestDataStatusRequest,
) (*pb.IngestDataStatusResponse, error) {

	return nil, nil
}
