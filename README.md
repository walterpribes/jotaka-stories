# Robô de stories — Jotaká

Publica automaticamente, todo dia às **11h (Brasília)**, o story "Estamos abertos" do dia
no **Instagram** e no **Facebook** do Jotaká. As artes ficam em `media/`, e o calendário
fica em `schedule.json`, de 04/11/2026 a 03/12/2026, uma por dia.

## Como funciona
- O GitHub Actions roda às 10h45 e às 11h30. A primeira execução espera até 11h e publica;
  a segunda só age se a primeira tiver atrasado ou falhado.
- O que já foi publicado fica registrado em `published.json`, então nada sai duas vezes.
- Para trocar uma arte ou uma data, edite o `schedule.json` ou substitua o arquivo em `media/`
  (JPEG, até 8 MB, 1080×1920).

## Configuração (uma vez só)

### 1. Criar o app na Meta
1. Acesse **developers.facebook.com** → **Meus apps** → **Criar app**.
2. Escolha o caso de uso para gerenciar e publicar em Páginas e Instagram (tipo **Empresa**)
   e vincule o portfólio empresarial do Jotaká.

### 2. Gerar o token da Página
1. Abra o **Explorador da Graph API** (developers.facebook.com/tools/explorer) e selecione o app.
2. Em **Permissões**, adicione: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   `instagram_basic`, `instagram_content_publish` e `business_management`.
3. Clique em **Gerar token de acesso** e autorize a Página e o Instagram do Jotaká.
4. Abra o **Depurador de token de acesso** (developers.facebook.com/tools/debug/accesstoken),
   cole o token e clique em **Estender token de acesso**. Copie o token longo.
5. De volta ao Explorador, cole o token longo e faça `GET me/accounts`. Na linha do Jotaká,
   copie o `access_token`: esse é o **token da Página**, que não expira.

### 3. Guardar no GitHub
Neste repositório: **Settings → Secrets and variables → Actions → New repository secret**
- Nome: `META_PAGE_TOKEN`
- Valor: o token da Página do passo 2.5

### 4. Testar sem publicar
**Actions → Stories Jotaká → Run workflow**
- `check`: confere o token, a Página e o Instagram.
- `dry-run`: manda a arte de hoje para o Instagram processar, sem publicar.

Se os dois derem certo, está pronto: às 11h do dia seguinte, o story sai sozinho.

## Requisitos
- O Instagram do Jotaká precisa ser conta **Comercial** (a API não publica stories de conta de Criador)
  e estar vinculado à Página do Facebook.
