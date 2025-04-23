package server

import (
	"context"

	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"
)

func (server *Server) CreateKnowledgeBase(
	ctx context.Context,
	req *pb.CreateKnowledgeBaseRequest,
) (*pb.KnowledgeBase, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	name := req.GetName()
	if name == "" {
		return nil, status.Error(codes.InvalidArgument, "please provide name for knowledge base")
	}

	knowledgeBase, err := server.store.CreateKnowledgeBase(
		ctx,
		database.CreateKnowledgeBaseParams{
			UserID: authPayload.UserId,
			Name:   name,
		},
	)

	if err != nil {
		if database.ErrorCode(err) == database.UniqueViolation {
			return nil, status.Error(codes.InvalidArgument, "please provide different name, as knowledge base already exists with this name")
		}
		return nil, status.Errorf(codes.Internal, "error creating knowledge base in database: %s", err.Error())
	}

	return &pb.KnowledgeBase{
		KnowledgeBaseId:   knowledgeBase.ID,
		KnowledgeBaseName: knowledgeBase.Name,
	}, nil
}

func (server *Server) ListKnowledgeBase(
	ctx context.Context,
	req *emptypb.Empty,
) (*pb.KnowledgeBaseResponse, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	knowledgeBases, err := server.store.ListUserKnowledgeBases(
		ctx,
		authPayload.UserId,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error retrieving knowledge bases from database: %s", err.Error())
	}

	knowledgeBaseForResponse := make([]*pb.KnowledgeBase, 0, len(knowledgeBases))

	for _, item := range knowledgeBases {
		knowledgeBase := &pb.KnowledgeBase{
			KnowledgeBaseId:   item.ID,
			KnowledgeBaseName: item.Name,
		}
		knowledgeBaseForResponse = append(knowledgeBaseForResponse, knowledgeBase)
	}

	return &pb.KnowledgeBaseResponse{
		KnowledgeBases: knowledgeBaseForResponse,
	}, nil
}

func (server *Server) DeleteKnowledgeBase(
	ctx context.Context,
	req *pb.DeleteKnowledgeBaseRequest,
) (*pb.Response, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	err = server.store.DeleteKnowledgeBase(
		ctx,
		database.DeleteKnowledgeBaseParams{
			KnowledgeBaseID: req.KnowledgeBaseId,
			UserID:          authPayload.UserId,
		},
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error deleting knowledge base: %s", err.Error())
	}

	return &pb.Response{
		Message: "successfully deleted knowledge base",
	}, nil
}
