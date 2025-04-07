// Code generated by protoc-gen-go. DO NOT EDIT.
// versions:
// 	protoc-gen-go v1.36.5
// 	protoc        v3.21.12
// source: ingest.proto

package pb

import (
	protoreflect "google.golang.org/protobuf/reflect/protoreflect"
	protoimpl "google.golang.org/protobuf/runtime/protoimpl"
	reflect "reflect"
	sync "sync"
	unsafe "unsafe"
)

const (
	// Verify that this generated code is sufficiently up-to-date.
	_ = protoimpl.EnforceVersion(20 - protoimpl.MinVersion)
	// Verify that runtime/protoimpl is sufficiently up-to-date.
	_ = protoimpl.EnforceVersion(protoimpl.MaxVersion - 20)
)

type IngestDataRequest struct {
	state         protoimpl.MessageState `protogen:"open.v1"`
	Files         []string               `protobuf:"bytes,1,rep,name=files,proto3" json:"files,omitempty"`
	unknownFields protoimpl.UnknownFields
	sizeCache     protoimpl.SizeCache
}

func (x *IngestDataRequest) Reset() {
	*x = IngestDataRequest{}
	mi := &file_ingest_proto_msgTypes[0]
	ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
	ms.StoreMessageInfo(mi)
}

func (x *IngestDataRequest) String() string {
	return protoimpl.X.MessageStringOf(x)
}

func (*IngestDataRequest) ProtoMessage() {}

func (x *IngestDataRequest) ProtoReflect() protoreflect.Message {
	mi := &file_ingest_proto_msgTypes[0]
	if x != nil {
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		if ms.LoadMessageInfo() == nil {
			ms.StoreMessageInfo(mi)
		}
		return ms
	}
	return mi.MessageOf(x)
}

// Deprecated: Use IngestDataRequest.ProtoReflect.Descriptor instead.
func (*IngestDataRequest) Descriptor() ([]byte, []int) {
	return file_ingest_proto_rawDescGZIP(), []int{0}
}

func (x *IngestDataRequest) GetFiles() []string {
	if x != nil {
		return x.Files
	}
	return nil
}

var File_ingest_proto protoreflect.FileDescriptor

var file_ingest_proto_rawDesc = string([]byte{
	0x0a, 0x0c, 0x69, 0x6e, 0x67, 0x65, 0x73, 0x74, 0x2e, 0x70, 0x72, 0x6f, 0x74, 0x6f, 0x12, 0x02,
	0x70, 0x62, 0x22, 0x29, 0x0a, 0x11, 0x49, 0x6e, 0x67, 0x65, 0x73, 0x74, 0x44, 0x61, 0x74, 0x61,
	0x52, 0x65, 0x71, 0x75, 0x65, 0x73, 0x74, 0x12, 0x14, 0x0a, 0x05, 0x66, 0x69, 0x6c, 0x65, 0x73,
	0x18, 0x01, 0x20, 0x03, 0x28, 0x09, 0x52, 0x05, 0x66, 0x69, 0x6c, 0x65, 0x73, 0x42, 0x10, 0x5a,
	0x0e, 0x69, 0x6e, 0x74, 0x65, 0x72, 0x6e, 0x61, 0x6c, 0x2f, 0x70, 0x62, 0x3b, 0x70, 0x62, 0x62,
	0x06, 0x70, 0x72, 0x6f, 0x74, 0x6f, 0x33,
})

var (
	file_ingest_proto_rawDescOnce sync.Once
	file_ingest_proto_rawDescData []byte
)

func file_ingest_proto_rawDescGZIP() []byte {
	file_ingest_proto_rawDescOnce.Do(func() {
		file_ingest_proto_rawDescData = protoimpl.X.CompressGZIP(unsafe.Slice(unsafe.StringData(file_ingest_proto_rawDesc), len(file_ingest_proto_rawDesc)))
	})
	return file_ingest_proto_rawDescData
}

var file_ingest_proto_msgTypes = make([]protoimpl.MessageInfo, 1)
var file_ingest_proto_goTypes = []any{
	(*IngestDataRequest)(nil), // 0: pb.IngestDataRequest
}
var file_ingest_proto_depIdxs = []int32{
	0, // [0:0] is the sub-list for method output_type
	0, // [0:0] is the sub-list for method input_type
	0, // [0:0] is the sub-list for extension type_name
	0, // [0:0] is the sub-list for extension extendee
	0, // [0:0] is the sub-list for field type_name
}

func init() { file_ingest_proto_init() }
func file_ingest_proto_init() {
	if File_ingest_proto != nil {
		return
	}
	type x struct{}
	out := protoimpl.TypeBuilder{
		File: protoimpl.DescBuilder{
			GoPackagePath: reflect.TypeOf(x{}).PkgPath(),
			RawDescriptor: unsafe.Slice(unsafe.StringData(file_ingest_proto_rawDesc), len(file_ingest_proto_rawDesc)),
			NumEnums:      0,
			NumMessages:   1,
			NumExtensions: 0,
			NumServices:   0,
		},
		GoTypes:           file_ingest_proto_goTypes,
		DependencyIndexes: file_ingest_proto_depIdxs,
		MessageInfos:      file_ingest_proto_msgTypes,
	}.Build()
	File_ingest_proto = out.File
	file_ingest_proto_goTypes = nil
	file_ingest_proto_depIdxs = nil
}
