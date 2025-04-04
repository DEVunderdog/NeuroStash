package token

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
)

func (tokenMaker *TokenMaker) GenerateAndSignAPIKey() (*string, []byte, error) {
	apiKeyBytes := make([]byte, 32)
	_, err := rand.Read(apiKeyBytes)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to generate random bytes in API key: %w", err)
	}

	hash := sha256.Sum256(apiKeyBytes)

	signature, err := rsa.SignPKCS1v15(rand.Reader, tokenMaker.privateKey, crypto.SHA256, hash[:])
	if err != nil {
		return nil, nil, fmt.Errorf("failed to sign API key: %w", err)
	}

	apiKey := base64.StdEncoding.EncodeToString(apiKeyBytes)

	return &apiKey, signature, nil
}

func (tokenMaker *TokenMaker) VerifyAPIKey(apiKey string, signature []byte) error {
	apiKeyBytes, err := base64.StdEncoding.DecodeString(apiKey)
	if err != nil {
		return fmt.Errorf("failed to decode API key: %w", err)
	}

	hash := sha256.Sum256(apiKeyBytes)

	err = rsa.VerifyPKCS1v15(tokenMaker.publicKey, crypto.SHA256, hash[:], signature)
	if err != nil {
		return fmt.Errorf("failed to verify signature: %w", err)
	}

	return nil
}
