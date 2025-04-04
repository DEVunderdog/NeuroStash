package token

import (
	"crypto/rsa"
)

type TokenMaker struct {
	publicKey  *rsa.PublicKey
	privateKey *rsa.PrivateKey
}

func NewTokenMaker(passphrase string, publicKey *string, privateKey []byte) (
	tokenMaker *TokenMaker,
	encryptedPrivateKey []byte,
	encodedPublicKey []byte,
	err error,
) {

	if publicKey != nil && privateKey != nil {
		decryptedKey, err := decryptPrivateKey(privateKey, []byte(passphrase))
		if err != nil {
			return nil, nil, nil, err
		}

		decodedPublicKey, err := decodePublicKey([]byte(*publicKey))
		if err != nil {
			return nil, nil, nil, err
		}

		tokenMaker = &TokenMaker{
			publicKey:  decodedPublicKey,
			privateKey: decryptedKey,
		}

	} else {
		var rsaPrivateKey *rsa.PrivateKey
		var rsaPublicKey *rsa.PublicKey
		rsaPrivateKey, rsaPublicKey, encryptedPrivateKey, encodedPublicKey, err = generateKeys(passphrase)
		if err != nil {
			return nil, nil, nil, err
		}

		tokenMaker = &TokenMaker{
			publicKey:  rsaPublicKey,
			privateKey: rsaPrivateKey,
		}
	}

	return
}
