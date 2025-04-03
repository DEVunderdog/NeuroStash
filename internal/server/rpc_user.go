package server

import (
	"context"

	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"github.com/DEVunderdog/neurostash/internal/utils"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func validateEmailRequest(email string) (violations []*errdetails.BadRequest_FieldViolation) {

	if err := utils.ValidateEmail(email); err != nil {
		violations = append(violations, fieldViolation("email", err))
	}

	return violations
}

func (server *Server) CreateUser(ctx context.Context, req *pb.CreateUserRequest) (*pb.ApiKeyResponse, error) {
	violations := validateEmailRequest(req.GetEmail())
	if violations != nil {
		return nil, invalidArgumentError(violations)
	}

	apiKey, signature, err := server.tokenMaker.GenerateAndSignAPIKey()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error generating api key: %s", err.Error())
	}

	err = server.store.RegisterUserTx(ctx, database.RegisterUserTxParams{
		Email:     req.GetEmail(),
		ApiKey:    *apiKey,
		Signature: signature,
	})

	if err != nil {
		if database.ErrorCode(err) == database.UniqueViolation {
			return nil, status.Error(codes.InvalidArgument, "user already exists with this email")
		}
		return nil, status.Errorf(codes.Internal, "error registering user: %s", err.Error())
	}

	return &pb.ApiKeyResponse{
		ApiKey: *apiKey,
	}, nil
}
