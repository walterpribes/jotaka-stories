"""Robô de feed do Jotaká: publica o post do dia (foto única ou carrossel, com legenda)
no Instagram e no Facebook, a partir de feed.json. Usa o mesmo segredo META_PAGE_TOKEN.

  python publish_feed.py              publica o post de hoje, no horário, se ainda não saiu
  python publish_feed.py --dry-run    prepara o próximo post no Instagram sem publicar
  python publish_feed.py --date AAAA-MM-DD   publica agora o post daquele dia
"""
import argparse, datetime as dt, json, os, sys, time
from zoneinfo import ZoneInfo
from publish import call, accounts, media_url, ROOT

TZ = ZoneInfo("America/Sao_Paulo")
STATE = os.path.join(ROOT, "published_feed.json")


def esperar(container):
    for _ in range(40):
        st = call("GET", container, fields="status_code").get("status_code")
        if st == "FINISHED":
            return container
        if st in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram recusou a mídia (status {st}).")
        time.sleep(5)
    raise SystemExit("Instagram demorou demais para processar.")


def ig_container(ig_id, item):
    urls = [media_url(f) for f in item["files"]]
    if len(urls) == 1:
        return esperar(call("POST", f"{ig_id}/media", image_url=urls[0], caption=item["caption"])["id"])
    filhos = [esperar(call("POST", f"{ig_id}/media", image_url=u, is_carousel_item="true")["id"]) for u in urls]
    return esperar(call("POST", f"{ig_id}/media", media_type="CAROUSEL",
                        children=",".join(filhos), caption=item["caption"])["id"])


def publish_ig(ig_id, item):
    return call("POST", f"{ig_id}/media_publish", creation_id=ig_container(ig_id, item))["id"]


def publish_fb(page_id, item):
    fotos = [call("POST", f"{page_id}/photos", url=media_url(f), published="false")["id"] for f in item["files"]]
    params = {"message": item["caption"]}
    for i, fid in enumerate(fotos):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": fid})
    return call("POST", f"{page_id}/feed", **params)["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date")
    a = ap.parse_args()

    page_id, page_name, ig_id, ig_user = accounts()
    print(f"Página: {page_name} · Instagram: @{ig_user}")
    now = dt.datetime.now(TZ); day = a.date or now.date().isoformat()
    sched = json.load(open(os.path.join(ROOT, "feed.json"), encoding="utf-8"))
    item = next((s for s in sched if s["date"] == day), None)
    if a.dry_run and not item and not a.date:
        item = next((s for s in sched if s["date"] >= day), None)
        if item: day = item["date"]
    if not item:
        print(f"Nenhum post de feed para {day}."); return
    print(f"{day} {item['time']}: {item['post']} ({len(item['files'])} imagem(ns))")

    if a.dry_run:
        c = ig_container(ig_id, item)
        print(f"Teste OK: o Instagram aceitou o post com a legenda (container {c}). Nada foi publicado.")
        return

    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    done = state.get(day, {})
    if done.get("instagram") and done.get("facebook"):
        print("Post de hoje já publicado."); return
    if not a.date:
        hh, mm = map(int, item["time"].split(":"))
        wait = (now.replace(hour=hh, minute=mm, second=0, microsecond=0) - now).total_seconds()
        if wait > 1800: print("Ainda é cedo; a próxima execução publica."); return
        if wait > 0: print(f"Aguardando {int(wait)}s…"); time.sleep(wait)

    erros = []
    for net, fn, acc in (("instagram", publish_ig, ig_id), ("facebook", publish_fb, page_id)):
        if done.get(net): continue
        try:
            done[net] = fn(acc, item); print(f"Publicado no {net}: {done[net]}")
        except SystemExit as e:
            erros.append(f"{net}: {e}"); print(f"Falhou no {net}: {e}")
    state[day] = done
    json.dump(state, open(STATE, "w"), indent=2)
    if erros: sys.exit("; ".join(erros))


if __name__ == "__main__":
    main()
