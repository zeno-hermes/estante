"""Formulários do domínio dos livros."""

from datetime import date, datetime

from django import forms

from .models import LinkLivro, Livro, NotaLivro


class DataBRWidget(forms.TextInput):
    """Campo de data em texto, sempre em dd/mm/aaaa, com ajuda no telemóvel.

    Não uso só `type="date"`: o campo nativo mostra a data no formato do sistema do
    utilizador (aparece mm/dd/yyyy num browser em inglês) e não há forma de o forçar
    pela página. Este widget dá as duas coisas:

    - o campo de escrita é de texto (dd/mm/aaaa sempre igual) e o JavaScript
      (`static/js/data-br.js`) insere as barras enquanto se escrevem só números —
      o teclado numérico do telemóvel passa a servir, sem depender da tecla «/»;
    - ao lado há um campo `type="date"` nativo, só para abrir o calendário do
      sistema. Não tem `name`, portanto não é submetido: quem guarda a data é o
      campo de texto.
    """

    template_name = "widgets/data_br.html"

    def __init__(self, attrs=None):
        padrao = {
            "placeholder": "dd/mm/aaaa",
            "inputmode": "numeric",
            "autocomplete": "off",
            "maxlength": "10",
            "pattern": r"[0-3][0-9]/[0-1][0-9]/[0-9]{4}",
            "size": 12,
            "data-campo-data-br": "1",
        }
        if attrs:
            padrao.update(attrs)
        super().__init__(padrao)

    def format_value(self, value):
        if value in (None, ""):
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        return super().format_value(value)

    def valor_iso(self, value):
        """A mesma data em aaaa-mm-dd, para o campo nativo (calendário)."""
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str) and value.strip():
            texto = value.strip()
            for formato in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(texto, formato).date().isoformat()
                except ValueError:
                    continue
        return ""

    def get_context(self, name, value, attrs):
        contexto = super().get_context(name, value, attrs)
        contexto["widget"]["valor_iso"] = self.valor_iso(value)
        return contexto


class EstrelasField(forms.TypedChoiceField):
    """Avaliação 1-5 apresentada como estrelas, devolvida como inteiro."""

    def __init__(self, **kwargs):
        escolhas = [("", "Sem avaliação")] + [
            (str(n), "★" * n + "☆" * (5 - n)) for n in range(1, 6)
        ]
        kwargs.setdefault("coerce", int)
        kwargs.setdefault("empty_value", None)
        kwargs.setdefault("required", False)
        super().__init__(choices=escolhas, **kwargs)


class LivroForm(forms.ModelForm):
    data_leitura = forms.DateField(
        label="Data de leitura",
        required=False,
        input_formats=["%d/%m/%Y", "%Y-%m-%d"],
        widget=DataBRWidget(
            attrs={
                "placeholder": "dd/mm/aaaa",
                "inputmode": "numeric",
                "autocomplete": "off",
                "size": 12,
            }
        ),
        help_text="Dia em que acabaste o livro, no formato dd/mm/aaaa "
        "(deixa vazio enquanto estiveres a ler).",
        error_messages={"invalid": "Escreve a data no formato dd/mm/aaaa (ex.: 14/08/2026)."},
    )
    avaliacao = EstrelasField(
        label="Avaliação",
        widget=forms.RadioSelect(attrs={"class": "estrelas"}),
    )

    class Meta:
        model = Livro
        fields = ["titulo", "autor", "data_leitura", "avaliacao", "estado"]
        widgets = {
            "titulo": forms.TextInput(
                attrs={"placeholder": "Título do livro", "autocomplete": "off", "autofocus": True}
            ),
            "autor": forms.TextInput(attrs={"placeholder": "Nome do autor", "autocomplete": "off"}),
        }
        labels = {"titulo": "Título", "autor": "Autor", "estado": "Estado"}

    def __init__(self, *args, utilizador=None, **kwargs):
        """O form precisa do dono para detetar duplicados.

        O `utilizador` não é um campo do formulário, por isso o Django exclui-o
        da validação da UniqueConstraint do modelo e essa verificação nunca
        corre aqui (relevante: `UniqueConstraint.validate` sai cedo quando um
        dos campos está em `exclude`). A duplicação tem de ser apanhada
        explicitamente, senão chega à BD e rebenta com IntegrityError.
        """
        super().__init__(*args, **kwargs)
        self.utilizador = utilizador or getattr(self.instance, "utilizador", None)

    def clean(self):
        dados = super().clean()
        titulo = dados.get("titulo")
        autor = dados.get("autor")
        data_leitura = dados.get("data_leitura")

        # Sem data de leitura (livro a ler) a BD permite duplicados (NULL não
        # colide com NULL); o formulário segue a mesma regra.
        if self.utilizador and titulo and autor and data_leitura:
            repetido = Livro.objects.filter(
                utilizador=self.utilizador,
                titulo=titulo,
                autor=autor,
                data_leitura=data_leitura,
            )
            if self.instance.pk:
                repetido = repetido.exclude(pk=self.instance.pk)
            if repetido.exists():
                raise forms.ValidationError(
                    "Já tens este livro registado com esta data de leitura. "
                    "Se foi uma releitura, escolhe a nova data."
                )
        return dados

    def clean_data_leitura(self):
        valor = self.cleaned_data.get("data_leitura")
        if valor and valor > date.today():
            raise forms.ValidationError("A data de leitura não pode estar no futuro.")
        return valor

    def clean_titulo(self):
        return (self.cleaned_data.get("titulo") or "").strip()

    def clean_autor(self):
        return (self.cleaned_data.get("autor") or "").strip()


class LinkLivroForm(forms.ModelForm):
    class Meta:
        model = LinkLivro
        fields = ["url", "descricao"]
        widgets = {
            "url": forms.URLInput(attrs={"placeholder": "https://…", "autocomplete": "off"}),
            "descricao": forms.TextInput(
                attrs={"placeholder": "Descrição (opcional)", "autocomplete": "off"}
            ),
        }
        labels = {"url": "Endereço", "descricao": "Descrição"}


class NotaLivroForm(forms.ModelForm):
    class Meta:
        model = NotaLivro
        fields = ["texto"]
        widgets = {
            "texto": forms.Textarea(
                attrs={"rows": 4, "placeholder": "O que queres guardar sobre este livro?"}
            )
        }
        labels = {"texto": "Nota"}
