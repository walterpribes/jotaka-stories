"""Robô de stories do Jotaká.

Publica no Instagram e no Facebook a arte agendada para o dia (schedule.json).
Roda pelo GitHub Actions. Segredos necessários (Settings → Secrets → Actions):
  META_PAGE_TOKEN  token de acesso da Página do Jotaká (longa duração)
Opcionais (descobertos sozinhos a partir do token, se ausentes):
  META_PAGE_ID, IG_USER_ID

Uso:
  python publish.py              publica a arte de hoje, se ainda não publicada
  python publish.py --check      só confere token, página e Instagram (não publica nada)
  python publish.py --dry-run    prepara a arte de hoje no Instagram sem publicar
  python publish.py --date 2026-11-04   força um dia específico
"""
import argparse, datetime as dt, json, os, sys, time
from zoneinfo import ZoneInfo
import urllib.request, urllib.parse, urllib.error

API = "https://graph.facebook.com/v26.0"
TZ = ZoneInfo("America/Sao_Paulo")
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "published.json")
ANTES = 14 * 60   # pode começar até 14 min antes do horário e esperar


def call(method, path, **params):
    # O token vai só no cabeçalho Authorization: nunca na URL, nunca impresso.
    token = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not token:
        raise SystemExit("Falta o segredo META_PAGE_TOKEN no GitHub.")
    headers = {"Authorization": f"Bearer {token}"}
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}", headers=headers)
    else:
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace").replace(token, "***")
        raise SystemExit(f"Erro da Meta em {method} {path}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Sem conexão com a Meta em {method} {path}: {e.reason}")


def accounts():
    page_id = os.environ.get("META_PAGE_ID")
    ig_id = os.environ.get("IG_USER_ID")
    me = call("GET", page_id or "me", fields="id,name,instagram_business_account{id,username}")
    page_id = me["id"]
    iga = me.get("instagram_business_account") or {}
    ig_id = ig_id or iga.get("id")
    return page_id, me.get("name"), ig_id, iga.get("username")


def media_url(path):
    repo = os.environ.get("GITHUB_REPOSITORY", "walterpribes/jotaka-stories")
    branch = os.environ.get("MEDIA_BRANCH", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"


def ig_container(ig_id, url):
    c = call("POST", f"{ig_id}/media", image_url=url, media_type="STORIES")["id"]
    for _ in range(30):
        st = call("GET", c, fields="status_code").get("status_code")
        if st == "FINISHED":
            return c
        if st in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram recusou a imagem (status {st}).")
        time.sleep(5)
    raise SystemExit("Instagram demorou demais para processar a imagem.")


def publish_ig(ig_id, url):
    c = ig_container(ig_id, url)
    return call("POST", f"{ig_id}/media_publish", creation_id=c)["id"]


def publish_fb(page_id, url):
    photo = call("POST", f"{page_id}/photos", url=url, published="false")["id"]
    return call("POST", f"{page_id}/photo_stories", photo_id=photo).get("post_id") or photo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--time", help="HH:MM, quando houver mais de um story no dia")
    a = ap.parse_args()

    page_id, page_name, ig_id, ig_user = accounts()
    print(f"Página: {page_name} ({page_id}) · Instagram: @{ig_user} ({ig_id})")
    if not ig_id:
        raise SystemExit("A Página não tem Instagram comercial vinculado.")
    if a.check:
        lim = call("GET", f"{ig_id}/content_publishing_limit", fields="quota_usage,config")
        print("Limite de publicação:", json.dumps(lim.get("data", lim)))
        print("Tudo certo: token e contas OK.")
        return

    now = dt.datetime.now(TZ)
    day = a.date or now.date().isoformat()
    sched = json.load(open(os.path.join(ROOT, "schedule.json"), encoding="utf-8"))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}

    def chave(s):
        # o story das 11h usa só a data (formato antigo); os outros horários usam "data hora"
        return s["date"] if s["time"] == "11:00" else f"{s['date']} {s['time']}"

    def feito(s):
        d = state.get(chave(s), {})
        return bool(d.get("instagram") and d.get("facebook"))

    def quando(s):
        hh, mm = map(int, s["time"].split(":"))
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)

    def publicar(item):
        url = media_url(item["file"])
        print(f"{item['date']} {item['time']}: {item['file']}")
        done = state.get(chave(item), {})
        if not a.date:
            wait = (quando(item) - dt.datetime.now(TZ)).total_seconds()
            if wait > 0:
                print(f"Aguardando {int(wait)}s até {item['time']}…")
                time.sleep(wait)
        errors = []
        for net, fn, acc in (("instagram", publish_ig, ig_id), ("facebook", publish_fb, page_id)):
            if done.get(net):
                continue
            try:
                done[net] = fn(acc, url)
                print(f"Publicado no {net}: {done[net]}")
            except SystemExit as e:
                errors.append(f"{net}: {e}")
                print(f"Falhou no {net}: {e}")
        state[chave(item)] = done
        json.dump(state, open(STATE, "w"), indent=2)
        if errors:
            raise SystemExit("; ".join(errors))

    do_dia = [s for s in sched if s["date"] == day and (not a.time or s["time"] == a.time)]
    if a.dry_run:
        item = do_dia[0] if do_dia else None
        if not item and not a.date:
            # No teste, usa a próxima arte do calendário.
            item = next((s for s in sched if (s["date"], s["time"]) >= (day, now.strftime("%H:%M"))), None)
        if not item:
            print(f"Nada agendado para {day}."); return
        url = media_url(item["file"])
        print(f"{item['date']} {item['time']}: {item['file']}")
        c = ig_container(ig_id, url)
        print(f"Teste OK: o Instagram aceitou a arte (container {c}). Nada foi publicado.")
        return

    hoje = now.date().isoformat()
    def na_hora(s):
        falta = (quando(s) - now).total_seconds()
        if day != hoje:
            return True                      # outro dia pedido à mão: publica tudo que falta
        return falta <= (0 if a.date else ANTES)  # hoje: o que já passou (atrasado) ou começa em até 14 min
    fila = [s for s in do_dia if not feito(s) and na_hora(s)]
    if not fila:
        print(f"Nada pendente para {day} agora.")
        return
    erros = []
    for s in fila:
        try:
            publicar(s)
        except SystemExit as e:
            erros.append(str(e))
    if erros:
        sys.exit("; ".join(erros))


if __name__ == "__main__":
    main()
