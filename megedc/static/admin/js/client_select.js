django.jQuery(document).ready(function(){
    django.jQuery('#id_chgc_client').change(function(){
        django.jQuery('#client_change_form').submit();
    });
});