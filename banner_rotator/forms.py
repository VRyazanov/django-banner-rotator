from django import forms
from banner_rotator.models import Banner

__author__ = 'orangeh'


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner

    def clean(self):
        campaign = self.cleaned_data.get('campaign')
        if campaign:
            self.cleaned_data['start_at'] = campaign.start_at
            self.cleaned_data['finish_at'] = campaign.finish_at
            if campaign.is_started:
                self.cleaned_data['in_rotation'] = True

        return self.cleaned_data