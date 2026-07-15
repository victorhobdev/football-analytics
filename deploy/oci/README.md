# Deploy no OCI Always Free

Runtime público mínimo: Caddy, Next.js, FastAPI e PostgreSQL. Airflow, MinIO e Metabase não são iniciados na VM.

## VM

- shape `VM.Standard.A1.Flex`, marcada como Always Free;
- 2 OCPUs e 12 GB de RAM;
- Ubuntu ARM;
- boot volume de 150 GB;
- IPv4 público;
- entrada TCP 22 somente do seu IP e TCP 80/443 da internet;
- não abrir 5432, 8010 ou 3001.

A Oracle limita atualmente o A1 Always Free a 2 OCPUs e 12 GB no total e pode recuperar instâncias consideradas ociosas. Confirme os limites no console antes de criar: <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm>.

## Preparação da VM

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"
```

Saia e entre novamente por SSH. Depois:

```bash
git clone <URL_DO_REPOSITORIO> football-analytics
cd football-analytics
cp deploy/oci/env.example deploy/oci/.env
mkdir -p deploy/oci/secrets
openssl rand -base64 36 > deploy/oci/secrets/postgres_password
chmod 600 deploy/oci/secrets/postgres_password
```

Edite `deploy/oci/.env` se o domínio ou o recorte de dados forem diferentes.

## Banco de dados

O volume local ocupa aproximadamente 43 GB. Gere um dump comprimido sem alterar o banco local:

```powershell
docker exec football_postgres pg_dump -U football -d football_dw -Fc -f /tmp/football_dw.dump
docker cp football_postgres:/tmp/football_dw.dump ./football_dw.dump
scp ./football_dw.dump ubuntu@IP_DA_VM:~/football_dw.dump
```

Na VM, inicialize somente o PostgreSQL e restaure em um volume vazio:

```bash
docker compose --env-file deploy/oci/.env -f deploy/oci/compose.yml up -d postgres
docker cp ~/football_dw.dump football-analytics-postgres-1:/tmp/football_dw.dump
docker compose --env-file deploy/oci/.env -f deploy/oci/compose.yml exec postgres \
  pg_restore -U football -d football_dw --no-owner --no-privileges /tmp/football_dw.dump
```

Não repita a restauração sobre um banco preenchido sem criar backup.

## Aplicação e HTTPS

Crie no Cloudflare um registro `A` para o domínio configurado em `APP_HOST`, apontando para o IPv4 público da VM. Durante a primeira emissão do certificado, use `Somente DNS`.

Copie `data/visual_assets` para a VM antes de subir os containers. O Compose falha de propósito quando o diretório não existe. Confirme ao menos os manifests e os assets de smoke:

```bash
test -r data/visual_assets/manifests/clubs.json
test -r data/visual_assets/manifests/competitions.json
test -r data/visual_assets/clubs/53.png
test -r data/visual_assets/clubs/503.png
test -r data/visual_assets/clubs/1024.png
test -r data/visual_assets/competitions/648.png
```

```bash
docker compose --env-file deploy/oci/.env -f deploy/oci/compose.yml up -d --build
docker compose --env-file deploy/oci/.env -f deploy/oci/compose.yml ps
curl -fsS "https://$(grep '^APP_HOST=' deploy/oci/.env | cut -d= -f2)/api/health"
curl -fsS -o /dev/null "https://$(grep '^APP_HOST=' deploy/oci/.env | cut -d= -f2)/visual-assets/clubs/53.png"
curl -fsS -o /dev/null "https://$(grep '^APP_HOST=' deploy/oci/.env | cut -d= -f2)/visual-assets/competitions/648.png"
```

Os serviços internos não publicam portas no host. O Caddy é o único ponto de entrada e renova o certificado HTTPS automaticamente.

## Atualização

```bash
git pull --ff-only
docker compose --env-file deploy/oci/.env -f deploy/oci/compose.yml up -d --build
```
