package main

import (
	"context"
	"errors"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/DEVunderdog/neurostash/internal/aws"
	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/logger"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"github.com/DEVunderdog/neurostash/internal/queue"
	"github.com/DEVunderdog/neurostash/internal/server"
	"github.com/DEVunderdog/neurostash/internal/token"
	"github.com/DEVunderdog/neurostash/internal/utils"
	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/rs/cors"
	"github.com/rs/zerolog/log"
	"golang.org/x/sync/errgroup"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
	"google.golang.org/protobuf/encoding/protojson"
)

var interruptSignals = []os.Signal{
	os.Interrupt,
	syscall.SIGTERM,
	syscall.SIGINT,
}

func main() {
	notifyContext, stop := signal.NotifyContext(context.Background(), interruptSignals...)
	defer stop()

	config, err := utils.LoadConfig("./app.yaml")
	if err != nil {
		log.Fatal().Err(err).Msg("error loading configuration")
	}

	connPool, err := pgxpool.New(notifyContext, config.DBSource)
	if err != nil {
		log.Fatal().Err(err).Msg("error creating database connection pool")
	}

	store := database.NewStore(connPool)

	var tokenMaker *token.TokenMaker
	activeKeys, err := store.GetActiveKey(notifyContext)
	if err != nil {
		if !errors.Is(err, pgx.ErrNoRows) {
			log.Fatal().Err(err).Msg("error getting active keys")
		}
	}

	if activeKeys.ID != 0 {
		tokenMaker, _, _, err = token.NewTokenMaker(config.Passphrase, &activeKeys.PublicKey, activeKeys.PrivateKey)
		if err != nil {
			log.Fatal().Err(err).Msg("error creating new token maker instance with existing keys")
		}
	} else {
		var encryptedPrivateKey []byte
		var encodedPublicKey []byte
		tokenMaker, encryptedPrivateKey, encodedPublicKey, err = token.NewTokenMaker(config.Passphrase, nil, nil)
		if err != nil {
			log.Fatal().Err(err).Msg("error creating new instance of token maker with new keys")
		}

		_, err = store.CreateEncryptionKeys(notifyContext, database.CreateEncryptionKeysParams{
			PublicKey:  string(encodedPublicKey),
			PrivateKey: encryptedPrivateKey,
			IsActive: pgtype.Bool{
				Valid: true,
				Bool:  true,
			},
		})
		if err != nil {
			log.Fatal().Err(err).Msg("error storing keys")
		}
	}

	awsClient, err := aws.NewAwsCloudClients(
		notifyContext,
		config.AwsAccessKey,
		config.AwsSecretKey,
		config.AwsRegion,
		config.AwsBucket,
		true,
	)
	if err != nil {
		log.Fatal().Err(err).Msg("error creating aws client")
	}

	queueClient := queue.NewQueueClient(config.QueueName, config.RabbitMqServerAddr)

	waitGroup, ctx := errgroup.WithContext(notifyContext)

	runGrpcServer(ctx, waitGroup, *config, store, tokenMaker, awsClient, queueClient)
	runGatewayServer(ctx, waitGroup, *config, store, tokenMaker, awsClient, queueClient)

	err = waitGroup.Wait()
	if err != nil {
		log.Error().Err(err).Msg("error from server group during execution")
	}

	log.Info().Msg("shutting down queue client...")
	if closeErr := queueClient.Close(); closeErr != nil {
		log.Error().Err(closeErr).Msg("error closing queue client")
	} else {
		log.Info().Msg("queue client shutdown")
	}

	if err != nil {
		os.Exit(1)
	}
}

func runGrpcServer(
	ctx context.Context,
	waitGroup *errgroup.Group,
	config utils.Config,
	store database.Store,
	tokenMaker *token.TokenMaker,
	awsClient *aws.AwsClients,
	queueClient *queue.QueueClient,
) {
	server, err := server.NewServer(ctx, store, config, tokenMaker, awsClient, queueClient)
	if err != nil {
		log.Fatal().Err(err).Msg("cannot create server")
	}

	grpcLogger := grpc.UnaryInterceptor(logger.GrpcLogger)
	grpcServer := grpc.NewServer(grpcLogger)

	pb.RegisterNeuroStashServer(grpcServer, server)
	reflection.Register(grpcServer)

	listener, err := net.Listen("tcp", config.GrpcServerAddress)
	if err != nil {
		log.Fatal().Err(err).Msg("cannot create listener")
	}

	waitGroup.Go(func() error {
		log.Info().Msgf("start gRPC server at %s", listener.Addr().String())

		err = grpcServer.Serve(listener)
		if err != nil {
			if errors.Is(err, grpc.ErrServerStopped) {
				return nil
			}
			log.Error().Err(err).Msg("gRPC server failed to serve")
			return err
		}
		return nil
	})

	waitGroup.Go(func() error {
		<-ctx.Done()
		log.Info().Msg("graceful shutdown gRPC server")

		grpcServer.GracefulStop()
		log.Info().Msg("gRPC server is stopped")

		return nil
	})
}

func runGatewayServer(
	ctx context.Context,
	waitGroup *errgroup.Group,
	config utils.Config,
	store database.Store,
	tokenMaker *token.TokenMaker,
	awsClient *aws.AwsClients,
	queueClient *queue.QueueClient,
) {
	server, err := server.NewServer(ctx, store, config, tokenMaker, awsClient, queueClient)
	if err != nil {
		log.Fatal().Err(err).Msg("cannot create server")
	}

	jsonOption := runtime.WithMarshalerOption(runtime.MIMEWildcard, &runtime.JSONPb{
		MarshalOptions: protojson.MarshalOptions{
			UseProtoNames: true,
		},
		UnmarshalOptions: protojson.UnmarshalOptions{
			DiscardUnknown: true,
		},
	})

	grpcMux := runtime.NewServeMux(jsonOption)

	err = pb.RegisterNeuroStashHandlerServer(ctx, grpcMux, server)
	if err != nil {
		log.Fatal().Err(err).Msg("cannot register handler server")
	}

	mux := http.NewServeMux()
	mux.Handle("/", grpcMux)

	c := cors.New(cors.Options{
		// AllowedOrigins: config.AllowedOrigins,
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{
			http.MethodHead,
			http.MethodOptions,
			http.MethodGet,
			http.MethodPost,
			http.MethodPut,
			http.MethodPatch,
			http.MethodDelete,
		},
		AllowedHeaders: []string{
			"Content-Type",
			"Authorization",
		},
		AllowCredentials: true,
	})

	handler := c.Handler(logger.HttpLogger(mux))

	httpServer := &http.Server{
		Handler: handler,
		Addr:    config.HttpServerAddress,
	}

	waitGroup.Go(func() error {
		log.Info().Msgf("start HTTP gateway server at %s", httpServer.Addr)
		err = httpServer.ListenAndServe()
		if err != nil {
			if errors.Is(err, http.ErrServerClosed) {
				return nil
			}
			log.Error().Err(err).Msg("HTTP gateway server failed to serve")
			return err
		}
		return nil
	})

	waitGroup.Go(func() error {
		<-ctx.Done()
		log.Info().Msg("graceful shutdown HTTP gateway server")

		err := httpServer.Shutdown(context.Background())
		if err != nil {
			log.Error().Err(err).Msg("failed to shutdown HTTP gateway server")
			return err
		}

		log.Info().Msg("HTTP gateway server is stopped")
		return nil
	})
}
