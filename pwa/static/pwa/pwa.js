/* Estante PWA — registo do service worker, instalação e limpeza ao sair. */

(function () {
  'use strict';

  const versao = document.body.dataset.cacheVersion || '';

  // 1. Service worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/pwa/sw.js', { scope: '/pwa/' }).catch(function (erro) {
        console.warn('Service worker não registado:', erro);
      });
    });
  }

  // 2. Convite a instalar — só enquanto a app não estiver instalada
  //
  // Não chega esconder o convite depois de instalada: as regras têm de estar
  // ao contrário, ou seja, mostrá-lo apenas quando há motivo. Quatro sinais,
  // por ordem de confiança:
  //   1. já corre como app instalada (`display-mode` / `navigator.standalone`);
  //   2. já foi instalada por aqui (`appinstalled` ou escolha «instalar»);
  //   3. o utilizador disse «Agora não» (fica gravado no telemóvel);
  //   4. o Android só oferece `beforeinstallprompt` quando ainda não está
  //      instalada — sem esse evento não há botão «Instalar» para oferecer.
  // O CSS tem a mesma regra para `display-mode` (ver pwa.css), que vale mesmo
  // antes de este script arrancar.
  const aviso = document.getElementById('aviso-instalar');
  const botaoInstalar = document.getElementById('botao-instalar');
  const botaoDispensar = document.getElementById('botao-dispensar-instalar');
  const CHAVE_DISPENSADO = 'estante:instalar-dispensado';
  const CHAVE_INSTALADA = 'estante:instalada';
  const MODOS_INSTALADOS = ['standalone', 'minimal-ui', 'fullscreen', 'window-controls-overlay'];
  let promptDiferido = null;

  function ler(chave) {
    try {
      return window.localStorage.getItem(chave);
    } catch (erro) {
      return null; // navegação privada sem armazenamento
    }
  }

  function gravar(chave) {
    try {
      window.localStorage.setItem(chave, '1');
    } catch (erro) {
      /* sem armazenamento: o convite pode voltar, mas nada parte */
    }
  }

  function jaInstalada() {
    if (ler(CHAVE_INSTALADA)) return true;
    if (window.navigator.standalone === true) return true; // iOS
    return MODOS_INSTALADOS.some(function (modo) {
      return window.matchMedia('(display-mode: ' + modo + ')').matches;
    });
  }

  function mostrarAviso() {
    if (!aviso || jaInstalada() || ler(CHAVE_DISPENSADO)) return;
    aviso.hidden = false;
  }

  function esconderAviso() {
    if (aviso) aviso.hidden = true;
  }

  window.addEventListener('beforeinstallprompt', function (evento) {
    evento.preventDefault();
    promptDiferido = evento;
    mostrarAviso();
  });

  window.addEventListener('appinstalled', function () {
    gravar(CHAVE_INSTALADA);
    esconderAviso();
  });

  if (botaoInstalar) {
    botaoInstalar.addEventListener('click', async function () {
      if (!promptDiferido) {
        esconderAviso();
        return;
      }
      promptDiferido.prompt();
      const escolha = await promptDiferido.userChoice;
      promptDiferido = null;
      if (escolha && escolha.outcome === 'accepted') gravar(CHAVE_INSTALADA);
      esconderAviso();
    });
  }

  if (botaoDispensar) {
    botaoDispensar.addEventListener('click', function () {
      gravar(CHAVE_DISPENSADO);
      esconderAviso();
    });
  }

  // iOS não tem `beforeinstallprompt`: as instruções manuais só aparecem a quem
  // ainda não tem a app instalada.
  const ehIOS =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (aviso && ehIOS && !jaInstalada() && !ler(CHAVE_DISPENSADO)) {
    aviso.querySelector('p').textContent =
      'Para instalar: toca em Partilha e depois em «Adicionar ao ecrã principal».';
    aviso.hidden = false;
    if (botaoInstalar) botaoInstalar.hidden = true;
  }

  // 3. Ao sair, apagar os dados guardados no telemóvel
  const formSair = document.querySelector('form[data-sair]');
  if (formSair && 'serviceWorker' in navigator) {
    formSair.addEventListener('submit', async function (evento) {
      if (!versao) return;
      evento.preventDefault();
      try {
        if (navigator.serviceWorker.controller) {
          navigator.serviceWorker.controller.postMessage({ tipo: 'limpar-dados' });
        } else if (window.caches) {
          await caches.delete('estante-dados-' + versao);
        }
      } catch (erro) {
        console.warn('Não foi possível limpar a cache:', erro);
      }
      formSair.submit();
    });
  }
})();
