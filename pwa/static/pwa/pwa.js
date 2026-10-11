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

  // 2. Convite a instalar (Android/Chrome), com instruções para iOS
  const aviso = document.getElementById('aviso-instalar');
  const botaoInstalar = document.getElementById('botao-instalar');
  let promptDiferido = null;

  window.addEventListener('beforeinstallprompt', function (evento) {
    evento.preventDefault();
    promptDiferido = evento;
    if (aviso) aviso.hidden = false;
  });

  if (botaoInstalar) {
    botaoInstalar.addEventListener('click', async function () {
      if (!promptDiferido) return;
      promptDiferido.prompt();
      await promptDiferido.userChoice;
      promptDiferido = null;
      if (aviso) aviso.hidden = true;
    });
  }

  const jaInstalada = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  const ehIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  if (aviso && ehIOS && !jaInstalada) {
    aviso.querySelector('p').textContent =
      'Para instalar: toca em Partilhar e depois em «Adicionar ao ecrã principal».';
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
