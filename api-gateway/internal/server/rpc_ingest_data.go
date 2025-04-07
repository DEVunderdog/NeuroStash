package server

import (
	"context"
	"encoding/json"

	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func (server *Server) IngestData(
	ctx context.Context,
	req *pb.IngestDataRequest,
) (*pb.Response, error) {
	payload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	files := req.GetFiles()
	if len(files) == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "bad request body please provide files")
	}

	objectKeys, err := server.store.GetFilesObjectKeys(ctx, database.GetFilesObjectKeysParams{
		UserID:    payload.UserId,
		Filenames: files,
	})
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error fetching files object key: %s", err.Error())
	}

	jsonData, err := json.Marshal(objectKeys)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error marshalling files into json: %s", err.Error())
	}

	err = server.queueClient.Push(jsonData)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error pushing message to queue: %s", err.Error())
	}

	return &pb.Response{
		Message: "requested accepted to ingest data",
	}, nil
}
