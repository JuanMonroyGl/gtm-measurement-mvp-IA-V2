<script>
  var element = {{Click Element}};
  var getClean = {{JS - Function - Format LowerCase}};
  var getClickText = {{JS - Click Text - Btn and A}};
  var getTextClose = {{JS - Function - Get Text Close}};

  var eventData = {
    activo: "bancolombia",
    seccion: "personas",
    flujo: "compra cartera",
    
  }
  
  function setDataEvent(data, e, cText, clean, getText) {
    if(e.closest('.cardSuperiorDesk .cardBannerDesk')) {
        // ----------------------------------------------------------------- Clic Link compra cartera con tu tarjeta de credito
        data['elemento'] = cText;
        data['ubicacion'] = "compra de cartera bancolombia";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Link', data)};
        return;
    }  else if(e.closest('.nav-tabs-wrapper .tab-item')) {
        // ----------------------------------------------------------------- Clic Card Tasas
        data['elemento'] = cText;
        data['ubicacion'] = "tasas";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Card', data)};
        return;
    } else if(e.closest('.contenedor-boton-general a')) {
        // ----------------------------------------------------------------- Clic Boton
        data['elemento'] = cText;
        data['ubicacion'] = "tasas";
        data['card seleccionada'] = "libre inversion";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Boton', data)};
        return;
    } else if(e.closest('.lista-tasas-condiciones a')) {
        // ----------------------------------------------------------------- Clic Link
        data['elemento'] = cText;
        data['ubicacion'] = "tasas";
        data['card seleccionada'] = "ten en cuenta";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Link', data)};
        return;
    } else if(e.closest('.accordion-content .lista-bullets a')) {
        // ----------------------------------------------------------------- Clic Link
        data['elemento'] = cText;
        data['ubicacion'] = "documentos";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Link', data)};
        return;
    } else if(e.closest('.accordion-group p a')) {
        // ----------------------------------------------------------------- Clic Link
        data['elemento'] = cText;
        data['ubicacion'] = "seguros";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Link', data)};
        return;
    }
  }

  setDataEvent(eventData, element, getClickText, getClean, getTextClose);
</script>