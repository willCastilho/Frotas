/* Layout "cabe na tela": ajusta a altura dos elementos .page-fit para o espaco
   disponivel no viewport, deixando a rolagem para os blocos .page-scroll
   internos. Em telas pequenas (<=760px) volta ao fluxo natural. Tambem trata os
   carrosseis (.carrossel-btn). */
(function () {
    var MOBILE = '(max-width: 760px)';

    function ajustarUm(el) {
        if (window.matchMedia(MOBILE).matches) {
            el.style.height = '';
            el.style.overflow = '';
            return;
        }
        var top = el.getBoundingClientRect().top;
        var altura = window.innerHeight - top - 14;
        el.style.height = Math.max(altura, 320) + 'px';
        el.style.overflow = 'hidden';
    }

    function ajustar() {
        document.querySelectorAll('.page-fit').forEach(ajustarUm);
    }

    function carrossel() {
        document.querySelectorAll('.carrossel-btn').forEach(function (btn) {
            if (btn.dataset.bound) return;
            btn.dataset.bound = '1';
            btn.addEventListener('click', function () {
                var track = document.getElementById(btn.dataset.alvo);
                if (!track) return;
                var dir = parseInt(btn.dataset.dir, 10) || 1;
                track.scrollBy({
                    left: dir * Math.round(track.clientWidth * 0.85),
                    behavior: 'smooth',
                });
            });
        });
    }

    function linhasClicaveis() {
        document.querySelectorAll('[data-href]').forEach(function (el) {
            if (el.dataset.bound) return;
            el.dataset.bound = '1';
            el.style.cursor = 'pointer';
            el.addEventListener('click', function (ev) {
                // Ignora cliques em links/botoes/formularios dentro do item.
                if (ev.target.closest('a, button, form, input, select')) return;
                window.location.href = el.dataset.href;
            });
        });
    }

    function iniciar() { carrossel(); linhasClicaveis(); ajustar(); }

    window.addEventListener('resize', ajustar);
    window.addEventListener('orientationchange', ajustar);
    window.addEventListener('load', ajustar);
    if (document.readyState !== 'loading') {
        iniciar();
    } else {
        document.addEventListener('DOMContentLoaded', iniciar);
    }
})();
