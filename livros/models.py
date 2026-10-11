from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Livro(models.Model):
    """Um livro lido (ou em leitura) pelo utilizador."""

    class Estado(models.TextChoices):
        A_LER = "a_ler", "A ler"
        LIDO = "lido", "Lido"
        ABANDONADO = "abandonado", "Abandonado"

    utilizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="livros",
        verbose_name="utilizador",
    )
    titulo = models.CharField("título", max_length=300)
    autor = models.CharField("autor", max_length=200)
    data_leitura = models.DateField(
        "data de leitura",
        null=True,
        blank=True,
        help_text="Dia em que acabaste o livro (deixa vazio enquanto estiveres a ler).",
    )
    avaliacao = models.PositiveSmallIntegerField(
        "avaliação",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 a 5 estrelas.",
    )
    estado = models.CharField(
        "estado",
        max_length=12,
        choices=Estado.choices,
        default=Estado.LIDO,
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "livro"
        verbose_name_plural = "livros"
        ordering = ["-data_leitura", "-criado_em"]
        constraints = [
            # Releituras são permitidas (a data distingue-as); o que não pode
            # existir é o registo exatamente duplicado. Nota: em SQL NULL não
            # colide com NULL, logo dois "a ler" com o mesmo título/autor passam.
            models.UniqueConstraint(
                fields=["utilizador", "titulo", "autor", "data_leitura"],
                name="unico_por_utilizador_titulo_autor_data",
            )
        ]
        indexes = [
            models.Index(fields=["utilizador", "-data_leitura"], name="livro_util_data_idx"),
        ]

    def __str__(self):
        return f"{self.titulo} — {self.autor}"

    @property
    def estrelas(self):
        """Avaliação em texto, sem repetir lógica nos templates."""
        return "★" * (self.avaliacao or 0) + "☆" * (5 - (self.avaliacao or 0))


class LinkLivro(models.Model):
    """URL associado a um livro. Relação 1:N (um livro tem vários URLs)."""

    livro = models.ForeignKey(
        Livro, on_delete=models.CASCADE, related_name="urls", verbose_name="livro"
    )
    url = models.URLField("endereço", max_length=500)
    descricao = models.CharField("descrição", max_length=150, blank=True)

    class Meta:
        verbose_name = "URL do livro"
        verbose_name_plural = "URLs do livro"
        ordering = ["id"]

    def __str__(self):
        return self.descricao or self.url


class NotaLivro(models.Model):
    """Nota de texto sobre um livro. Relação 1:N (um livro tem várias notas)."""

    livro = models.ForeignKey(
        Livro, on_delete=models.CASCADE, related_name="notas", verbose_name="livro"
    )
    texto = models.TextField("nota")
    criado_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "nota do livro"
        verbose_name_plural = "notas do livro"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.texto[:60]
