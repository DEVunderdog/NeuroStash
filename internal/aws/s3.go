package aws

import (
	"context"
	"errors"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	v4 "github.com/aws/aws-sdk-go-v2/aws/signer/v4"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
)

const expiry = 600

type PresignedResponse struct {
	PutObjectResponse  *v4.PresignedHTTPRequest
	PostObjectResponse *s3.PresignedPostRequest
}

func (awsClient *AwsClients) PutObject(
	ctx context.Context,
	objectKey string,
) (*PresignedResponse, error) {
	request, err := awsClient.presignClient.PresignPutObject(ctx, &s3.PutObjectInput{
		Bucket: aws.String(awsClient.BucketName),
		Key:    aws.String(objectKey),
	},
		func(opts *s3.PresignOptions) {
			opts.Expires = time.Duration(expiry * int64(time.Second))
		})

	if err != nil {
		return nil, err
	}

	return &PresignedResponse{
		PutObjectResponse:  request,
		PostObjectResponse: nil,
	}, nil
}

func (awsClient *AwsClients) PostObject(
	ctx context.Context,
	objectKey string,
) (*PresignedResponse, error) {
	request, err := awsClient.presignClient.PresignPostObject(
		ctx,
		&s3.PutObjectInput{
			Bucket: aws.String(awsClient.BucketName),
			Key:    aws.String(objectKey),
		},
		func(opts *s3.PresignPostOptions) {
			opts.Expires = time.Duration(expiry * int64(time.Second))
		},
	)

	if err != nil {
		return nil, err
	}

	return &PresignedResponse{
		PutObjectResponse:  nil,
		PostObjectResponse: request,
	}, nil

}

func (awsClient *AwsClients) ObjectExists(
	ctx context.Context,
	objectKey string,
) (bool, error) {
	_, err := awsClient.s3Client.HeadObject(
		ctx,
		&s3.HeadObjectInput{
			Bucket: &awsClient.BucketName,
			Key:    &objectKey,
		},
	)
	if err == nil {
		return true, nil
	} else {
		var notFound *types.NotFound
		if errors.As(err, &notFound) {
			return false, nil
		} else {
			return false, err
		}
	}
}
