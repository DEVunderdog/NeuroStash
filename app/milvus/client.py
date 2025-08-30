from pymilvus import MilvusClient, DataType, Function, FunctionType
from app.core.config import Settings
from app.constants.globals import MODEL_DIMENSION
from app.milvus.entity import CollectionSchemaEntity, auto_generated_fields
from typing import List
from dataclasses import asdict
import logging

logger = logging.getLogger(__name__)


class MilvusOps:
    def __init__(self, settings: Settings):
        self.settings = settings
        token = None

        if self.settings.MILVUS_USER and self.settings.MILVUS_PASSWORD:
            token = f"{self.settings.MILVUS_USER}:{self.settings.MILVUS_PASSWORD}"

        self.client = MilvusClient(uri=self.settings.MILVUS_URL, token=token)

    def create_database(self, name: str):
        try:
            self.client.create_database(db_name=name)
        except Exception:
            logger.error("error creating database in milvus", exc_info=True)
            raise

    def get_database(self, name: str):
        data = self.client.describe_database(db_name=name)
        if data["name"] == "":
            return None
        else:
            return data

    def list_database(self) -> List[str]:
        return self.client.list_databases()

    def drop_database(self, name: str):
        try:
            self.client.drop_database(db_name=name)
        except Exception:
            logger.error("error droping milvus database", exc_info=True)
            raise

    def create_collection(self, collection_name: str):
        try:
            schema = self.client.create_schema()
            schema.add_field(
                field_name="id",
                datatype=DataType.VARCHAR,
                max_length=36,
                is_primary=True,
                auto_id=False,
            )
            schema.add_field(
                field_name="text_dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=MODEL_DIMENSION,
            )
            schema.add_field(
                field_name="text_sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR,
            )
            schema.add_field(
                field_name="category",
                datatype=DataType.VARCHAR,
                max_length=100,
                nullable=False,
            )
            schema.add_field(
                field_name="object_key",
                datatype=DataType.VARCHAR,
                max_length=2048,
                nullable=False,
            )
            schema.add_field(
                field_name="file_name",
                datatype=DataType.VARCHAR,
                max_length=255,
                nullable=False,
            )
            schema.add_field(
                field_name="text_content",
                datatype=DataType.VARCHAR,
                nullable=False,
            )
            schema.add_field(
                field_name="user_id",
                datatype=DataType.INT64,
                nullable=False,
            )
            schema.add_field(
                field_name="file_id",
                datatype=DataType.INT64,
                nullable=False,
            )

            bm25_function = Function(
                name="text_bm25_emb",
                input_field_names=["text_content"],
                output_field_names=["text_sparse_vector"],
                function_type=FunctionType.BM25,
            )

            schema.add_function(bm25_function)

            index_params = self.client.prepare_index_params()

            index_params.add_index(
                field_name="text_dense_vector",
                index_name="text_dense_index",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 32, "efConstruction": 400},
            )

            index_params.add_index(
                field_name="text_sparse_vector",
                index_name="text_sparse_index",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="BM25",
                params={
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    "bm25_k1": 1.2,
                    "bm25_b": 0.75,
                },
            )

            index_params.add_index(
                field_name="user_id", index_type="INVERTED", index_name="user_index"
            )

            index_params.add_index(
                field_name="file_id", index_type="INVERTED", index_name="file_index"
            )

            index_params.add_index(
                field_name="category", index_type="BITMAP", index_name="category_index"
            )

            self.client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
            )

        except Exception:
            logger.error("error creating schema for database", exc_info=True)
            raise

    def drop_collection(self, collection_name: str):
        try:
            self.client.drop_collection(collection_name=collection_name)
        except Exception:
            logger.error("error dropping collection", exc_info=True)
            raise

    def upsert_into_collection(
        self, collection_name: str, data: List[CollectionSchemaEntity]
    ):
        data_to_upsert = []
        for entity in data:
            entity_dict = asdict(entity)

            cleaned_dict = {
                key: value
                for key, value in entity_dict.items()
                if key not in auto_generated_fields
            }
            data_to_upsert.append(cleaned_dict)

        try:
            self.client.upsert(collection_name=collection_name, data=data_to_upsert)
            logger.info("successfully inserted the data into collection")
        except Exception as e:
            logger.error(f"error inserting data into collection: {e}", exc_info=e)
            raise

    def delete_entities_record(self, collection_name: str, filter: str):
        try:
            self.client.delete(collection_name=collection_name, filter=filter)
            logger.info("successfully processed deletion of entities collection record")
        except Exception as e:
            logger.error(
                f"error deleting entities collection record: {e}", exc_info=True
            )
            raise
