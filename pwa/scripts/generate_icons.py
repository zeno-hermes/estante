"""Gera os ícones da PWA (Pillow).

    .venv/bin/python pwa/scripts/generate_icons.py

Produz quatro ficheiros em pwa/static/pwa/icons/:
- icon-192.png / icon-512.png — ícones `any`
- maskable-192.png / maskable-512.png — ícones `maskable`

Os `maskable` são arte separada de propósito: o Android recorta-os à forma do
launcher, por isso têm fundo a sangrar até às bordas (sem cantos redondos nem
transparência) e o glifo dentro da zona segura de ~80 %.
"""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parent.parent / "static" / "pwa" / "icons"

VERDE = (47, 94, 78, 255)
VERDE_ESCURO = (35, 74, 61, 255)
BRANCO = (255, 255, 255, 255)


def desenhar_livro(imagem, escala, deslocamento):
    """Desenha o livro (duas páginas) na imagem, com o tamanho indicado."""
    desenho = ImageDraw.Draw(imagem, "RGBA")
    lado = 320 * escala
    altura = 250 * escala
    x = deslocamento
    y = deslocamento
    raio = int(28 * escala)
    folga = int(10 * escala)

    metade = (lado - folga) / 2
    desenho.rounded_rectangle(
        [x, y, x + metade, y + altura], radius=raio, fill=BRANCO
    )
    desenho.rounded_rectangle(
        [x + metade + folga, y, x + lado, y + altura],
        radius=raio,
        fill=(255, 255, 255, 165),
    )


def gerar(tamanho, destino, maskable=False):
    imagem = Image.new("RGBA", (tamanho, tamanho), VERDE)
    desenho = ImageDraw.Draw(imagem)

    if maskable:
        # fundo a sangrar até às bordas, glifo na zona segura (60 % do lado)
        desenhar_livro(imagem, escala=tamanho / 512 * 0.6, deslocamento=tamanho * 0.2)
    else:
        # cantos redondos suaves e glifo um pouco maior
        raio = int(tamanho * 0.18)
        mascara = Image.new("L", (tamanho, tamanho), 0)
        ImageDraw.Draw(mascara).rounded_rectangle([0, 0, tamanho, tamanho], radius=raio, fill=255)
        fundo = Image.new("RGBA", (tamanho, tamanho), VERDE_ESCURO)
        imagem = Image.composite(fundo, imagem, mascara)
        desenhar_livro(imagem, escala=tamanho / 512 * 0.72, deslocamento=tamanho * 0.14)

    imagem.save(destino, format="PNG", optimize=True)
    return destino


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    gerados = []
    for tamanho in (192, 512):
        gerados.append(gerar(tamanho, DESTINO / f"icon-{tamanho}.png"))
        gerados.append(gerar(tamanho, DESTINO / f"maskable-{tamanho}.png", maskable=True))
    for caminho in gerados:
        with Image.open(caminho) as imagem:
            print(f"{caminho.relative_to(DESTINO.parent.parent.parent)}: {imagem.size[0]}x{imagem.size[1]} {imagem.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
