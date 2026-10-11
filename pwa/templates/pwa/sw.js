/* Service worker da Estante.
 *
 * Regras:
 * - estáticos: cache-first (com a versão no nome da cache, para poder invalidar);
 * - páginas de /pwa/: network-first — dados nunca são servidos da cache quando há
 *   rede; em falha, mostra-se o que estava guardado COM um aviso visível;
 * - tudo o resto (site desktop, admin): passa ao lado, o service worker não interfere.
 *
 * A versão vem do servidor (PWA_CACHE_VERSION). Subir essa constante cria caches
 * novas e apaga as antigas no `activate`.
 */

const CACHE_ESTATICOS = 'estante-estaticos-{{ cache_version }}';
const CACHE_DADOS = 'estante-dados-{{ cache_version }}';

const ESTATICOS = [
  '/static/pwa/pwa.css',
  '/static/pwa/pwa.js',
  '/static/pwa/icons/icon-192.png',
  '/static/pwa/icons/icon-512.png',
  '/pwa/manifest.webmanifest',
  '/pwa/offline/',
];

self.addEventListener('install', (evento) => {
  evento.waitUntil((async () => {
    const cache = await caches.open(CACHE_ESTATICOS);
    await cache.addAll(ESTATICOS);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil((async () => {
    const nomes = await caches.keys();
    const atuais = [CACHE_ESTATICOS, CACHE_DADOS];
    await Promise.all(nomes.filter((nome) => !atuais.includes(nome)).map((nome) => caches.delete(nome)));
    await self.clients.claim();
  })());
});

function respostaComAviso(copia) {
  return copia.text().then((texto) => {
    const agora = new Date().toLocaleString('pt-PT');
    const aviso = '<div class="aviso-offline" role="status">Sem ligação — a mostrar dados guardados em ' + agora + '</div>';
    // Injetado logo a seguir ao cabeçalho (e não no fim do documento, onde ficava
    // fora do ecrã). Assim fica no fluxo da página e o CSS cola-o por baixo da barra.
    if (texto.includes('</header>')) {
      return montarResposta(texto.replace('</header>', '</header>' + aviso), copia);
    }
    if (/<body[^>]*>/.test(texto)) {
      return montarResposta(texto.replace(/(<body[^>]*>)/, '$1' + aviso), copia);
    }
    return montarResposta(texto + aviso, copia);
  });
}

function montarResposta(corpo, copia) {
  const cabecalhos = new Headers(copia.headers);
  cabecalhos.set('X-Estante-Offline', '1');
  return new Response(corpo, { status: copia.status, statusText: copia.statusText, headers: cabecalhos });
}

async function estaticoCacheFirst(pedido) {
  const emCache = await caches.match(pedido);
  if (emCache) return emCache;
  const resposta = await fetch(pedido);
  if (resposta.ok) {
    const cache = await caches.open(CACHE_ESTATICOS);
    cache.put(pedido, resposta.clone());
  }
  return resposta;
}

async function paginaNetworkFirst(pedido) {
  try {
    const resposta = await fetch(pedido);
    const guardavel = resposta.ok && !resposta.redirected && !pedido.url.includes('/entrar/');
    if (guardavel) {
      const cache = await caches.open(CACHE_DADOS);
      // `await` obrigatório: o handler termina quando devolvemos a resposta e o
      // service worker pode ser terminado antes de a escrita acabar (a cache
      // ficava vazia e o modo offline não funcionava — visto só em produção).
      await cache.put(pedido, resposta.clone());
      return resposta;
    }
    // 5xx = servidor alcançável mas aplicação em baixo (ex.: Nginx a devolver 502
    // porque o serviço parou). Para quem está no telemóvel isso é o mesmo que não
    // haver rede: mostra-se o que estava guardado, com aviso, em vez de uma página
    // de erro crua do proxy.
    if (resposta.status < 500) return resposta;
  } catch (erro) {
    // falha de rede: cai no mesmo caminho
  }

  const emCache = await caches.match(pedido);
  if (emCache) return respostaComAviso(emCache);
  const offline = await caches.match('/pwa/offline/');
  if (offline) return offline;
  return new Response('Sem ligação.', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}

self.addEventListener('fetch', (evento) => {
  const pedido = evento.request;
  if (pedido.method !== 'GET') return;

  const url = new URL(pedido.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/static/')) {
    evento.respondWith(estaticoCacheFirst(pedido));
    return;
  }

  if (url.pathname.startsWith('/pwa/') && !url.pathname.endsWith('/sw.js')) {
    evento.respondWith(paginaNetworkFirst(pedido));
  }
});

/* O shell mobile pede a limpeza dos dados guardados ao terminar sessão, para não
 * deixar listas de livros no telemóvel depois de sair. */
self.addEventListener('message', (evento) => {
  if (evento.data && evento.data.tipo === 'limpar-dados') {
    evento.waitUntil(caches.delete(CACHE_DADOS));
  }
});
