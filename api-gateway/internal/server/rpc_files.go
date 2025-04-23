package server

import (
	"context"
	"fmt"
	"strconv"
	"strings"

	"github.com/DEVunderdog/neurostash/internal/aws"
	database "github.com/DEVunderdog/neurostash/internal/database/sqlc"
	"github.com/DEVunderdog/neurostash/internal/pb"
	"github.com/DEVunderdog/neurostash/internal/types"
	"github.com/DEVunderdog/neurostash/internal/utils"
	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func (server *Server) UploadFiles(ctx context.Context, req *pb.UploadRequest) (*pb.UploadResponse, error) {
	authPayload, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	files := req.GetFiles()
	inclusionPrefix := req.GetInclusionPrefix()

	if inclusionPrefix == "" {
		return nil, status.Errorf(codes.InvalidArgument, "please provide inclusion prefix")
	}

	if len(files) == 0 {
		return nil, status.Error(codes.InvalidArgument, "please provide files to upload")
	}

	response := make(map[string]*pb.PresignedUrls, len(files))
	fileNames := make([]string, 0, len(files))
	objectKeys := make([]string, 0, len(files))
	var objectUrls *aws.PresignedResponse
	presignedUrls := &pb.PresignedUrls{}

	for _, item := range files {
		var err error
		unq_id := uuid.New().String()

		cleanedPrefix := strings.Trim(inclusionPrefix, "/")
		objectKey := fmt.Sprintf("%s/%s/%s", cleanedPrefix, strconv.Itoa(int(authPayload.UserId)), unq_id)

		if req.Multipart {
			objectUrls, err = server.awsClient.PostObject(ctx, objectKey)
			if err != nil {
				return nil, status.Errorf(codes.Internal, "error getting presigned url for PostObject: %s", err.Error())
			}

			presignedUrls.Url = objectUrls.PostObjectResponse.URL
			formDataValues := &pb.PresignedUrls_FormDataValues{
				FormDataValues: &pb.FormDataValuesMap{
					FormValues: make(map[string]string),
				},
			}
			for key, value := range objectUrls.PostObjectResponse.Values {
				formDataValues.FormDataValues.FormValues[key] = value
			}
			presignedUrls.UrlsMetadata = formDataValues
		} else {
			objectUrls, err = server.awsClient.PutObject(ctx, objectKey)
			if err != nil {
				return nil, status.Errorf(codes.Internal, "error getting presigned url for PutObject: %s", err.Error())
			}
			presignedUrls.Url = objectUrls.PutObjectResponse.URL
			signedHeaders := &pb.PresignedUrls_SignedHeaders{
				SignedHeaders: &pb.SignedHeadersMap{
					Headers: make(map[string]*pb.Values),
				},
			}
			presignedUrls.Method = objectUrls.PutObjectResponse.Method
			for headerKey, headerValue := range objectUrls.PutObjectResponse.SignedHeader {
				signedHeaders.SignedHeaders.Headers[headerKey] = &pb.Values{
					Values: headerValue,
				}
			}
		}

		fileNames = append(fileNames, item)
		objectKeys = append(objectKeys, objectKey)
	}

	result, err := server.store.CreateEmptyDocuments(ctx, database.CreateEmptyDocumentsParams{
		UserID:     authPayload.UserId,
		FileNames:  fileNames,
		ObjectKeys: objectKeys,
		LockStatus: types.Locked,
		OpStatus:   database.OperationStatusPENDING,
	})
	if err != nil {
		if database.ErrorCode(err) == database.UniqueViolation {
			return nil, status.Error(codes.InvalidArgument, "please provided unique names for file")
		}
		return nil, status.Errorf(codes.Internal, "error creating empty documents in database: %s", err.Error())
	}

	for _, item := range result {
		presignedUrls.FileId = item.ID
		if !item.UpdatedAt.Valid {
			return nil, status.Errorf(codes.Internal, "invalid timestamp: %v", item.UpdatedAt.Time)
		}
		protoTime, err := utils.ConvertPgTimestampToProtoTimestamp(&item.UpdatedAt)
		if err != nil {
			return nil, status.Errorf(codes.Internal, "error converting database timestamp to proto timestamp: %s", err.Error())
		}
		presignedUrls.UpdatedAt = protoTime
		response[item.FileName] = presignedUrls
	}

	return &pb.UploadResponse{
		Files: response,
	}, nil
}

func (server *Server) ConfirmUploadStatus(ctx context.Context, req *pb.UploadStatusRequest) (*pb.Response, error) {
	_, err := server.authorizeUser(ctx)
	if err != nil {
		return nil, unauthenticatedError(err)
	}

	files := req.GetFiles()
	updatedAt := req.GetUpdatedAt()

	if updatedAt == nil {
		return nil, status.Errorf(codes.InvalidArgument, "please provide updated_at")
	}

	if len(files) == 0 {
		return nil, status.Error(codes.InvalidArgument, "please provide files to confirm status")
	}

	filesToBeDeleted := make([]int32, 0, len(files))
	successfulFiles := make([]int32, 0, len(files))

	for fileID, status := range files {
		if status {
			successfulFiles = append(successfulFiles, fileID)
		} else {
			filesToBeDeleted = append(filesToBeDeleted, fileID)
		}
	}

	pgTypeTime, err := utils.ConvertProtoTimestampToPgTimestamp(updatedAt)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error converting time %s", err.Error())
	}

	err = server.store.FileStatusTx(ctx, database.FileStatusTxParams{
		FilesToBeDeleted:  filesToBeDeleted,
		FilesToBeUnlocked: successfulFiles,
		UpdatedAt:         *pgTypeTime,
	})

	if err != nil {
		return nil, status.Errorf(codes.Internal, "error updating the database with status: %s", err.Error())
	}

	return &pb.Response{
		Message: "successfully updated the status of the files",
	}, nil
}
