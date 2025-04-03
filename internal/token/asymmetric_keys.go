package token

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"fmt"
	"io"

	"golang.org/x/crypto/pbkdf2"
)

const iter = 300000

func generateRsaKeys() (*rsa.PrivateKey, *rsa.PublicKey, error) {
	privateKey, err := rsa.GenerateKey(rand.Reader, 4096)
	if err != nil {
		return nil, nil, err
	}

	return privateKey, &privateKey.PublicKey, nil
}

func encryptPrivateKey(privateKey *rsa.PrivateKey, passphrase []byte) ([]byte, error) {
	privateKeyBytes, err := x509.MarshalPKCS8PrivateKey(privateKey)
	if err != nil {
		return nil, err
	}

	block := &pem.Block{
		Type:  "ENCRYPTED PRIVATE KEY",
		Bytes: privateKeyBytes,
	}

	blockBytes := pem.EncodeToMemory(block)

	salt := make([]byte, 16)
	if _, err := io.ReadFull(rand.Reader, salt); err != nil {
		return nil, err
	}

	key := pbkdf2.Key(passphrase, salt, iter, 32, sha256.New)

	c, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(c)
	if err != nil {
		return nil, err
	}

	nonce := make([]byte, gcm.NonceSize())

	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}

	cipherText := gcm.Seal(nil, nonce, blockBytes, nil)

	result := make([]byte, len(salt)+len(nonce)+len(cipherText))

	copy(result, salt)
	copy(result[len(salt):], nonce)
	copy(result[len(salt)+len(nonce):], cipherText)

	return result, err

}

func decryptPrivateKey(encryptedKey []byte, passphrase []byte) (*rsa.PrivateKey, error) {
	if len(encryptedKey) < 16+12 {
		return nil, errors.New("invalid encrypted key format")
	}

	salt := encryptedKey[:16]

	key := pbkdf2.Key(passphrase, salt, iter, 32, sha256.New)

	c, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(c)
	if err != nil {
		return nil, err
	}

	nonce := encryptedKey[16 : 16+gcm.NonceSize()]
	cipherText := encryptedKey[16+gcm.NonceSize():]

	pemBytes, err := gcm.Open(nil, nonce, cipherText, nil)
	if err != nil {
		return nil, err
	}

	block, _ := pem.Decode(pemBytes)

	privateKeyInterface, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, err
	}

	privateKey, ok := privateKeyInterface.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("not an RSA private key")
	}

	return privateKey, nil
}

func encodePublicKey(publicKey *rsa.PublicKey) ([]byte, error) {
	pubASN1, err := x509.MarshalPKIXPublicKey(publicKey)
	if err != nil {
		return nil, err
	}

	pubBytes := pem.EncodeToMemory(&pem.Block{
		Type:  "PUBLIC KEY",
		Bytes: pubASN1,
	})

	if pubBytes == nil {
		return nil, fmt.Errorf("failed to encode public key")
	}

	return pubBytes, err
}

func decodePublicKey(key[]byte) (*rsa.PublicKey, error) {
	block, _ := pem.Decode(key)

	if block == nil {
		return nil, errors.New("failed to decode PEM block containing public key")
	}

	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, err
	}

	switch pub := pub.(type) {
	case *rsa.PublicKey:
		return pub, nil
	default:
		return nil, errors.New("not an RSA based public key")
	}
}

func generateKeys(passphrase string) (
	rsaPrivateKey *rsa.PrivateKey,
	rsaPublicKey *rsa.PublicKey,
	encryptedPrivateKey []byte,
	publicKeyPem []byte,
	err error,
) {
	rsaPrivateKey, rsaPublicKey, err = generateRsaKeys()
	if err != nil {
		return nil, nil, nil, nil, err
	}

	encryptedPrivateKey, err = encryptPrivateKey(rsaPrivateKey, []byte(passphrase))
	if err != nil {
		return nil, nil, nil, nil, err
	}

	publicKeyPem, err = encodePublicKey(rsaPublicKey)
	if err != nil {
		return nil, nil, nil, nil, err
	}

	return

}
