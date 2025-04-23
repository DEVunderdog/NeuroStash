package server

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/DEVunderdog/neurostash/internal/token"
	"github.com/jackc/pgx/v5"
	"google.golang.org/grpc/metadata"
)

const (
	authorizationHeader = "authorization"
	authorizationBearer = "bearer"
)

func (server *Server) authorizeUser(ctx context.Context) (*token.Payload, error) {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return nil, fmt.Errorf("missing metadata")
	}

	values := md.Get(authorizationHeader)
	if len(values) == 0 {
		return nil, fmt.Errorf("missing authorization header")
	}

	authHeader := values[0]
	fields := strings.Fields(authHeader)
	if len(fields) < 2 {
		return nil, fmt.Errorf("invalid authorization header format")
	}

	authType := strings.ToLower(fields[0])
	if authType != authorizationBearer {
		return nil, fmt.Errorf("unsupported authorization type: %s", authType)
	}

	apiKey := fields[1]

	payload, err := server.store.GetApiKeyPayload(ctx, []byte(apiKey))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, errors.New("provided api key doesn't exists")
		}
		return nil, fmt.Errorf("error getting api key payload")
	}

	err = server.tokenMaker.VerifyAPIKey(apiKey, payload.Signature)
	if err != nil {
		return nil, err
	}

	return &token.Payload{
		ApiKey: apiKey,
		UserId: payload.UserID,
	}, nil
}
