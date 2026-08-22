package main

import (
	"log"

	"github.com/labstack/echo/v5"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/api"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
)

func main() {
	e := echo.New()

	service := api.NewService()
	openapi.RegisterHandlers(e, service)

	if err := e.Start(":8080"); err != nil {
		log.Fatalf("server error: %v", err)
	}
}