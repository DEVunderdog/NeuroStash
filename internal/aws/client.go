package aws

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
	"github.com/aws/smithy-go"
	"github.com/aws/smithy-go/logging"
)

type AwsClients struct {
	BucketName    string
	presignClient *s3.PresignClient
	s3Client      *s3.Client
}

type defaultLogger struct {
	logger *log.Logger
}

func (l defaultLogger) Logf(classification logging.Classification, format string, args ...interface{}) {
	l.logger.Printf(format, args...)
}

func NewAwsCloudClients(
	ctx context.Context,
	accessKey, secret, region, bucketName string,
	logModeEnable bool,
) (*AwsClients, error) {

	cfgOptions := []func(*config.LoadOptions) error{
		config.WithRegion(region),
		config.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider(accessKey, secret, ""),
		),
	}

	if logModeEnable {
		// We need a separate stream for the AWS Logs hence we chose os.Stderr
		stdLogger := log.New(os.Stderr, "AWS_SDK", log.LstdFlags)
		loggerWrapper := defaultLogger{logger: stdLogger}

		cfgOptions = append(
			cfgOptions,
			config.WithClientLogMode(aws.LogRequestWithBody|aws.LogResponseWithBody),
			config.WithLogger(loggerWrapper),
		)
	}

	sdkConfig, err := config.LoadDefaultConfig(ctx, cfgOptions...)
	if err != nil {
		return nil, fmt.Errorf("error loading AWS SDK configuration: %w", err)
	}

	s3Client, err := newS3Client(ctx, sdkConfig, bucketName)
	if err != nil {
		return nil, fmt.Errorf("error creating s3 object storage client: %w", err)
	}

	preSignClient := s3.NewPresignClient(s3Client)

	return &AwsClients{
		BucketName:    bucketName,
		presignClient: preSignClient,
		s3Client:      s3Client,
	}, nil
}

func newS3Client(ctx context.Context, config aws.Config, bucketName string) (*s3.Client, error) {
	s3Client := s3.NewFromConfig(config)

	_, err := s3Client.HeadBucket(ctx, &s3.HeadBucketInput{
		Bucket: &bucketName,
	})

	if err != nil {
		var apiError smithy.APIError
		if errors.As(err, &apiError) {
			switch apiError.(type) {
			case *types.NotFound:
				return nil, fmt.Errorf("bucket %s is not available: %w", bucketName, err)
			default:
				return nil, fmt.Errorf("either you do not have access to bucket or another error occurred: %w", err)
			}
		}
	}

	return s3Client, nil
}
