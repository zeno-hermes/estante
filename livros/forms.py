"""Formulários do domínio dos livros."""

from datetime import date

from django import forms

from .models import LinkLivro, Livro, NotaLivro


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
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Dia em que acabaste o livro (deixa vazio enquanto estiveres a ler).",
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
