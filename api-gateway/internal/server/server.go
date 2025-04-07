package server

import (
	"context"

	"github.com/DEVunderdog/neurostash/internal/aws"
	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"github.com/DEVunderdog/neurostash/internal/queue"
	"github.com/DEVunderdog/neurostash/internal/token"
	"github.com/DEVunderdog/neurostash/internal/utils"
)

type Server struct {
	pb.UnimplementedNeuroStashServer
	config      *utils.Config
	store       database.Store
	tokenMaker  *token.TokenMaker
	awsClient   *aws.AwsClients
	queueClient *queue.QueueClient
}

func NewServer(
	ctx context.Context,
	store database.Store,
	config utils.Config,
	tokenMaker *token.TokenMaker,
	awsClient *aws.AwsClients,
	queueClient *queue.QueueClient,
) (server *Server, err error) {

	server = &Server{
		config:      &config,
		store:       store,
		tokenMaker:  tokenMaker,
		awsClient:   awsClient,
		queueClient: queueClient,
	}

	return
}
