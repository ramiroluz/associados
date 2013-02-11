# encoding: utf-8
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse, reverse_lazy
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.views.generic.list import ListView
from django.views.generic.edit import FormView

from app.members.models import Category, Member
from app.members.forms import MemberForm, UserForm
from app.authemail.forms import RegisterForm

import json

class MemberListView(ListView):
    model = Member

    def get(self, request, *args, **kwargs):
        self.query = request.GET.get('q')
        self.category = request.GET.get('category')

        queryset = self.get_queryset()

        if self.query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=self.query) |
                Q(user__last_name__icontains=self.query)
            )

        if self.category:
            queryset = queryset.filter(category__id=self.category)

        self.queryset = queryset

        return super(MemberListView, self).get(request, args, kwargs)

    def get_context_data(self, **kwargs):
        context = super(MemberListView, self).get_context_data(**kwargs)
        if self.query:
            context['q'] = self.query
        if self.category:
            context['active_category'] = int(self.category)
        context['categories'] = Category.objects.all()
        return context


class SignupView(FormView):
    template_name = 'members/member_signup.html'
    form_class = RegisterForm
    success_url = reverse_lazy('members-form')

    def form_valid(self, form):
        form.save()
        user = authenticate(
            username=self.request.POST['email'],
            password=self.request.POST['password1'])
        login(self.request, user)
        messages.success(self.request, 'Você está cadastrado! Complete os seus dados para\
            prosseguir com o registro na associação!')
        return super(SignupView, self).form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Houve um erro ao cadastrar-se')
        return super(SignupView, self).form_invalid(form)


@login_required
def member_form(request):
    try:
        member = Member.objects.get(user=request.user)
    except Member.DoesNotExist:
        member = Member()
    user_form = UserForm(request.POST or None, instance=request.user)
    member_form = MemberForm(request.POST or None, instance=member)
    if request.POST:
        if member_form.is_valid() and user_form.is_valid():
            member_form.save(user=request.user)
            user_form.save()
            messages.add_message(request, messages.INFO, 'Seus dados foram atualizados com sucesso')
            return HttpResponseRedirect(reverse('members-dashboard'))
        else:
            messages.add_message(request, messages.ERROR, 'Ocorreu um erro ao tentar salvar seus dados. verifique o form abaixo.')

    return render(
        request,
        "members/member_form.html", {
            "member_form": member_form,
            'user_form': user_form
        }
    )

def _retrieve_parameters(request, parameters_dict):
    received_parameters = {}

    querydict = request.GET
    for query_key in querydict:
        for param_key, param_value in parameters_dict.items():
            if param_key == query_key:
                received_parameters[param_value] = querydict[query_key]

    return received_parameters


def _search_member(params):
    result = ''
    member = Member.objects.filter(**params)

    if member:
        days_to_next_payment = member[0].get_days_to_next_payment(member[0].get_last_payment())
        if days_to_next_payment > 0:
            result = 'ativo'
        else:
            result = 'inativo'
    else:
        result = 'invalido'
    return {'status': result}


def member_status(request):
    valid_parameters = {
        'first_name': 'user__first_name',
        'last_name': 'user__last_name',
        'email': 'user__email',
        'cpf': 'cpf',
        'phone': 'phone',
        'organization': 'organization'
    }
    response = ''
    params = _retrieve_parameters(request, valid_parameters)

    if params == {}:
        error_message = u'nenhum parâmetro válido informado. Opções: %s' % valid_parameters.keys()
        response = {'error': error_message}
    else:
        response = _search_member(params)

    return HttpResponse(json.dumps(response), content_type='application/json')


@login_required
def dashboard(request):
    try:
        payment_results = request.user.member.get_payment_check_list()
    except Member.DoesNotExist:
        messages.add_message(request, messages.INFO, 'Para acessar os dashboard, você precisa completar os seus dados')
        return HttpResponseRedirect(reverse('members-form'))

    return render(
        request,
        "members/dashboard.html",
        payment_results
    )
