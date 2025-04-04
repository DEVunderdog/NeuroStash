package utils

import (
	"fmt"
	"regexp"
)

var emailRegex = regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)

func validateEmailRegex(value string) error {
	if !emailRegex.MatchString(value) {
		return fmt.Errorf("invalid email format")
	}
	return nil
}

func ValidateEmail(value string) error {

	return validateEmailRegex(value)
}
