use actix_web::{web, App, HttpServer};
use std::env;

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let port = env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let api_key = env::var("API_KEY").expect("API_KEY must be set");

    HttpServer::new(|| {
        App::new()
            .route("/", web::get().to(|| async { "Hello!" }))
    })
    .bind(format!("0.0.0.0:{}", port))?
    .run()
    .await
}
