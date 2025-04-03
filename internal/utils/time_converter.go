package utils

import (
	"fmt"

	"github.com/jackc/pgx/v5/pgtype"
	"google.golang.org/protobuf/types/known/timestamppb"
)

func ConvertPgTimestampToProtoTimestamp(ts *pgtype.Timestamptz) (*timestamppb.Timestamp, error) {

	if ts.InfinityModifier != pgtype.Finite {
		return nil, fmt.Errorf("cannot convert infinite timestamp (modifier: %d), to protobuf timestamp", ts.InfinityModifier)
	}

	protoTime := timestamppb.New(ts.Time)

	err := protoTime.CheckValid()
	if err != nil {
		return nil, fmt.Errorf("time value %v is outside the valid range for protobuf timestamp: %w", ts.Time, err)
	}

	return protoTime, nil
}

func ConvertProtoTimestampToPgTimestamp(pts *timestamppb.Timestamp) (*pgtype.Timestamptz, error) {
	
	err := pts.CheckValid()
	if err != nil {
		return &pgtype.Timestamptz{}, fmt.Errorf("input protobuf timestamp is invalid; %w", err)
	}

	languageAgnosticTime := pts.AsTime()

	return &pgtype.Timestamptz{
		Time:             languageAgnosticTime,
		InfinityModifier: pgtype.Finite,
		Valid:            true,
	}, nil

}
