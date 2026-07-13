/**
 * Worker v4.0 — proxy de feed via ?url=
 *
 * Problema: URLSearchParams / query parsers tratam & como separador de parâmetros do Worker.
 * URLs de destino com & (ex.: Nyaa) ou ?channel_id= (YouTube) eram truncadas.
 *
 * Solução: após "url=" na query string, usar o restante bruto até o fim da URL da requisição
 * (substring), e opcionalmente decodeURIComponent uma vez se o cliente encodou o destino.
 */
export default {
  async fetch(request, env) {
    // Proteção anti open-proxy: se PROXY_SECRET estiver definido no Worker,
    // exige o header X-Proxy-Secret igual. Sem isso, qualquer um poderia usar
    // este Worker como proxy aberto.
    const secret = env && env.PROXY_SECRET;
    if (secret) {
      const provided = request.headers.get("X-Proxy-Secret");
      if (provided !== secret) {
        return new Response("Forbidden", { status: 403 });
      }
    }

    const reqUrl = request.url;
    const qAt = reqUrl.indexOf("?");
    if (qAt === -1) {
      return new Response("Use ?url=https://...", { status: 400 });
    }

    const query = reqUrl.slice(qAt + 1);
    const marker = "url=";
    const mPos = query.indexOf(marker);
    if (mPos === -1) {
      return new Response("Missing url= parameter", { status: 400 });
    }

    let target = query.slice(mPos + marker.length);
    try {
      target = decodeURIComponent(target);
    } catch {
      /* mantém literal */
    }

    if (!target.startsWith("http://") && !target.startsWith("https://")) {
      return new Response("url must be an absolute http(s) URL", { status: 400 });
    }

    const outHeaders = new Headers(request.headers);
    outHeaders.delete("Host");
    // Não repassa o segredo do proxy para o site de destino.
    outHeaders.delete("X-Proxy-Secret");

    return fetch(target, {
      method: request.method,
      headers: outHeaders,
      body: request.body,
      redirect: "follow",
    });
  },
};
