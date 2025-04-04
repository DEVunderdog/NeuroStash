package utils

import (
	"github.com/spf13/viper"
)

type Config struct {
	DBSource          string   `mapstructure:"DB_SOURCE"`
	Passphrase        string   `mapstructure:"PASSPHRASE"`
	Audience          string   `mapstructure:"AUDIENCE"`
	Issuer            string   `mapstructure:"ISSUER"`
	GrpcServerAddress string   `mapstructure:"GRPC_SERVER_ADDRESS"`
	AllowedOrigins    []string `mapstructure:"ALLOWED_ORIGINS"`
	HttpServerAddress string   `mapstructure:"HTTP_SERVER_ADDRESS"`
	AwsAccessKey      string   `mapstructure:"AWS_ACCESS_KEY"`
	AwsSecretKey      string   `mapstructure:"AWS_SECRET_KEY"`
	AwsRegion         string   `mapstructure:"AWS_REGION"`
	AwsBucket         string   `mapstructure:"AWS_BUCKET"`
}

func LoadConfig(path string) (config *Config, err error) {
	viper.SetConfigFile(path)

	viper.AutomaticEnv()

	err = viper.ReadInConfig()
	if err != nil {
		return
	}

	err = viper.Unmarshal(&config)
	if err != nil {
		return
	}

	return
}
