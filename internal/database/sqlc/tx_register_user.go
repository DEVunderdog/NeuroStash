package database

import "context"

type RegisterUserTxParams struct {
	Email     string
	ApiKey    string
	Signature []byte
}

func (store *SQLStore) RegisterUserTx(ctx context.Context, arg RegisterUserTxParams) error {

	return store.execTx(ctx, func(q *Queries) error {
		var err error

		user, err := q.RegisterUser(ctx, arg.Email)
		if err != nil {
			return err
		}

		_, err = q.CreateApiKey(ctx, CreateApiKeyParams{
			UserID:     user.ID,
			Credential: []byte(arg.ApiKey),
			Signature:  arg.Signature,
		})

		if err != nil {
			return err
		}

		return nil
	})
}
