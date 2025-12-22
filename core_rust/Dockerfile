# ESTÁGIO 1: Compilação (Pesado)
FROM rustlang/rust:nightly as builder

WORKDIR /usr/src/gandalf_core

# Dica para cachear dependências
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release
RUN rm -rf src

# Agora copia o código real
COPY . .
# Força a recompilação do binário real
RUN touch src/main.rs
RUN cargo build --release

# ESTÁGIO 2: Execução (Leve)
FROM debian:bookworm-slim

# Instala libssl e libpq
RUN apt-get update && apt-get install -y libssl-dev libpq-dev && rm -rf /var/lib/apt/lists/*

# COPIAR O BINÁRIO
# IMPORTANTE: Verifique se o nome "nome_do_projeto_rust" abaixo bate com o name = "..." no seu Cargo.toml
COPY --from=builder /usr/src/gandalf_core/target/release/lucas /usr/local/bin/gandalf_core

CMD ["gandalf_core"]
