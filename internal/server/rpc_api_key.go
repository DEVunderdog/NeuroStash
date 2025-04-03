package server

import (
	"context"

	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"
)

func (server *Server) CreateApiKey(ctx context.Context, req *emptypb.Empty) (*pb.ApiKeyResponse, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	apiKey, signature, err := server.tokenMaker.GenerateAndSignAPIKey()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to create api key: %s", err.Error())
	}

	_, err = server.store.CreateApiKey(ctx, database.CreateApiKeyParams{
		UserID:     authPayload.UserId,
		Credential: []byte(*apiKey),
		Signature:  signature,
	})

	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to create api key: %s", err.Error())
	}

	return &pb.ApiKeyResponse{
		ApiKey: *apiKey,
	}, nil
}

func (server *Server) ListApiKeys(ctx context.Context, req *emptypb.Empty) (*pb.ListApiKeyResponse, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	apiKeys, err := server.store.ListApiKeys(ctx, authPayload.UserId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error listing api keys: %s", err.Error())
	}

	convertedApiKeys := make([]string, len(apiKeys))

	for index, item := range apiKeys {
		convertedApiKeys[index] = string(item)
	}

	return &pb.ListApiKeyResponse{
		ApiKeys: convertedApiKeys,
	}, nil
}

func (server *Server) DeleteApiKey(ctx context.Context, req *pb.DeleteApiKeyRequest) (*pb.Response, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	apiKey := req.GetApiKey()
	if apiKey == "" {
		return nil, status.Errorf(codes.InvalidArgument, "please provide api key")
	}

	if authPayload.ApiKey == apiKey {
		return nil, status.Error(codes.InvalidArgument, "please provide api key which is other than the api key used for authorization")
	}

	result, err := server.store.DeleteApiKey(ctx, database.DeleteApiKeyParams{
		Credential: []byte(req.GetApiKey()),
		UserID:     authPayload.UserId,
	})

	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to deleted api key: %s", err.Error())
	}

	if result.RowsAffected() == 0 {
		return &pb.Response{
			Message: "cannot find api key",
		}, nil
	}

	return &pb.Response{
		Message: "successfully deleted the api key",
	}, nil
}
