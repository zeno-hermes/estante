/* Campo de data dd/mm/aaaa: máscara enquanto se escreve e calendário nativo.
 *
 * Existe porque o teclado numérico do telemóvel não tem a tecla «/»: quem escreve
 * só números vê as barras aparecerem sozinhas (14 08 2026 -> 14/08/2026). O campo
 * `type="date"` ao lado serve apenas para abrir o calendário do sistema — não tem
 * `name`, logo não é submetido.
 */
(function () {
  'use strict';

  function formatar(digitos) {
    const d = digitos.slice(0, 8);
    if (d.length <= 2) return d;
    if (d.length <= 4) return d.slice(0, 2) + '/' + d.slice(2);
    return d.slice(0, 2) + '/' + d.slice(2, 4) + '/' + d.slice(4);
  }

  // Conta quantos dígitos existem antes da posição do cursor, para o repor
  // depois de reformatar (quem corrige um dígito no meio não salta para o fim).
  function digitosAntes(texto, posicao) {
    return (texto.slice(0, posicao).match(/\d/g) || []).length;
  }

  function posicaoParaDigito(texto, quantos) {
    if (quantos <= 0) return 0;
    let contados = 0;
    for (let i = 0; i < texto.length; i += 1) {
      if (/\d/.test(texto[i])) {
        contados += 1;
        if (contados === quantos) return i + 1;
      }
    }
    return texto.length;
  }

  function ligarMascara(campo) {
    campo.addEventListener('input', function (evento) {
      const anterior = campo.value;
      const posicao = campo.selectionStart === null ? anterior.length : campo.selectionStart;
      const antes = digitosAntes(anterior, posicao);
      const novo = formatar(anterior.replace(/\D/g, ''));

      if (novo === anterior) return;
      campo.value = novo;
      // só mexe no cursor quando o utilizador está a escrever/apagar no fim
      if (!evento.inputType || !evento.inputType.startsWith('delete')) {
        const destino = posicaoParaDigito(novo, antes);
        try {
          campo.setSelectionRange(destino, destino);
        } catch (erro) {
          /* campo sem suporte a seleção: fica no fim */
        }
      }
    });

    // ao sair do campo, completa «14/08/26» -> «14/08/2026»
    campo.addEventListener('blur', function () {
      const digitos = campo.value.replace(/\D/g, '');
      if (digitos.length === 6) {
        const comAno = digitos.slice(0, 4) + (digitos.slice(4, 6) >= '30' ? '19' : '20') + digitos.slice(4, 6);
        campo.value = formatar(comAno);
      }
    });
  }

  function ligarCalendario(campo, nativo) {
    if (!nativo) return;

    // abrir o calendário já na data escrita
    nativo.addEventListener('focus', function () {
      const atual = campo.value.replace(/\D/g, '');
      if (atual.length === 8) {
        nativo.value = atual.slice(4, 8) + '-' + atual.slice(2, 4) + '-' + atual.slice(0, 2);
      }
    });

    // o campo nativo está invisível: um clique nele abre o calendário onde existir
    // showPicker (Chrome/Android). Onde não existir (iOS), o toque abre o seletor
    // nativo por si — é para isso que o campo continua a ser um <input type="date">.
    nativo.addEventListener('click', function () {
      if (typeof nativo.showPicker === 'function') {
        try {
          nativo.showPicker();
        } catch (erro) {
          /* sem gesto de utilizador válido: o toque trata do assunto */
        }
      }
    });

    nativo.addEventListener('change', function () {
      if (!nativo.value) return;
      const [ano, mes, dia] = nativo.value.split('-');
      campo.value = dia + '/' + mes + '/' + ano;
      campo.dispatchEvent(new Event('input', { bubbles: true }));
      campo.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  function iniciar() {
    document.querySelectorAll('input[data-campo-data-br]').forEach(function (campo) {
      if (campo.dataset.dataLigada === '1') return;
      campo.dataset.dataLigada = '1';
      const nativo = document.querySelector('input[data-campo-data-calendario][data-para="' + campo.id + '"]');
      ligarMascara(campo);
      ligarCalendario(campo, nativo);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
  document.addEventListener('zeno:conteudo-atualizado', iniciar);
})();
