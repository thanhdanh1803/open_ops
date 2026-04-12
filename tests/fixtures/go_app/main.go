package main

import (
	"os"
	"github.com/gin-gonic/gin"
)

func main() {
	port := os.Getenv("PORT")
	apiKey := os.Getenv("API_KEY")

	r := gin.Default()
	r.GET("/", func(c *gin.Context) {
		c.JSON(200, gin.H{"message": "Hello"})
	})
	r.Run(":" + port)
}
