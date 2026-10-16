//@charset "gbk";
var tjid = $('#tjid').attr('value');
//独家选股
function openDiv($dom) {
    if (tjid == 'yjkb') {
        TA.log({ 'id': 'db_55e411a6_323' });
    } else if (tjid == 'yjyg') {
        TA.log({ 'id': 'db_55ebdaf8_6' });
    } else if (tjid == 'yjgg') {
        TA.log({ 'id': 'db_55efe48c_985' });
    } else if (tjid == 'yypl') {
        TA.log({ 'id': 'db_55f29c3f_227' });
    } else if (tjid == 'sgpx') {
        TA.log({ 'id': 'db_55f13d06_111' });
    }
    $dom.show();
}

function closeDiv($dom) {
    $dom.hide();
}

$(function() {
    //菜单栏
    var curidx = $('.inner-nav a').index($('.inner-nav a.cur'));
    var $subNav = $('.sub-nav');
    $subNav.find('span').each(function() {
        $(this).attr('blockwidth', $(this).outerWidth())
    });
    $subNav.hide();
    $('.inner-nav a').mouseenter(function() {
        $(this).addClass('cur').siblings().removeClass('cur');
        var navName = $(this).attr('nav') + '-list';
        var $navList = $subNav.find('.' + navName);
        if ($navList.length > 0) {
            var top = $(this).offset().top + $(this).outerHeight();
            var left = $(this).offset().left;
            // var maxLeft = $('.container').offset().left + 1200;
            var maxLeft = $('.inner-nav a:last').offset().left + $('.inner-nav a:last').outerWidth();
            var width = parseFloat($navList.attr('blockwidth'));
            if (width + left > maxLeft) {
                left = maxLeft - width;
            }
            $subNav.css({
                'top': top,
                'left': left,
                'zIndex': 10
            }).show();
            $navList.show().siblings().hide();
        } else {
            $subNav.hide();
        }
    })
    $('.nav').mouseleave(function() {
        $('.inner-nav a').eq(curidx).addClass('cur').siblings().removeClass('cur');
        $subNav.hide();
    });

    //表格选中列突出显示
    function setTableCss() {
        var colidx = $('.m-table th.cur').attr('colidx');
        var trLen = $('.m-table tbody tr').length;
        $('.m-table tbody tr').each(function(i) {
            if (i == 0) {
                $(this).find('td').eq(colidx).addClass('selfirst');
            }
            if (i == trLen - 1) {
                $(this).find('td').eq(colidx).addClass('sellast');
            }
            $(this).find('td').eq(colidx).addClass('selected');
        });
    }
    setTableCss();

    //表格高亮
    $('.m-table td').live('mouseenter', function() {
        var index = $(this).index();
        var $tr = $('.m-table tr');
        var href = window.location.href;
        if (href.indexOf('yjkb') > -1) {
            href = 'yjkb';
        }
        if (href.indexOf('yjgg') > -1) {
            href = 'yjgg';
        }
        if (href.indexOf('sgpx') > -1) {
            href = 'sgpx';
        }
        switch (href) {
            case 'yjkb':
            case 'yjgg':
            case 'sgpx':
                //十字光标
                $tr.each(function() {
                    $(this).find('td').removeClass('highlight').eq(index).addClass('highlight');
                })
                $tr.removeClass('highlight');
                $(this).parent('tr').addClass('highlight');
                break;
            default:
                //一字光标
                $(this).parent('tr').addClass('highlight');
                break;
        }
    }).live('mouseleave', function() {
        $('.m-table tr,.m-table td').removeClass('highlight');
    });

    //URL参数处理
    var diffRequest = function(param) {
        var request = eval('(' + $('#request').val() + ')');
        var requestQuery = $('#requestQuery').val() ? '?' + $('#requestQuery').val() : '';
        var params = [];
        for (var i in param) {
            request[i] = param[i];
        }
        for (i in request) {
            if (request[i] && (typeof(param.page) != 'undefined' || i != 'page')) {
                params.push(i + '/' + request[i]);
            }
        }
        return params.join('/') + '/' + requestQuery;
    };


    //页面内容变换
    var changeContent = function(param, callback) {
        var baseUrl = $('#baseUrl').val();
        var url = '/' + baseUrl + '/' + param;

        var getDataFunc = function(){
            $('.page-loading').ajaxStart(function() {
                var top = $('.page-main .J-ajax-table thead').outerHeight() + 5;
                var height = $('.page-main .J-ajax-table tbody').outerHeight();
                $('.page-loading .mask,.page-loading .loading-img').css('height', height);
                $(this).css({
                    'top': top,
                    'height': height
                }).show();
            });
            $.ajax({
                url: url,
                type: 'get',
                dataType: 'html',
                success: function(data) {
                    $('#J-ajax-main').html(data);
                    $('.page-loading').hide();
                    setTableCss();
                    tableThead();
                    if (tjid == 'gnzjl' || tjid == 'hyzjl') {
                        initHighchart('charts1', JS_DATA);
                    }
                }
            });
        }

        l2Show.func.registerShowFunc(function(){
            getDataFunc();
        },function(){
            url = url + "free/1/";
            getDataFunc();
        });
    };

    function getReport() {
        var report = $('#report').attr('date');
        return report;
    }

    function getBoard() {
        var board = '';
        $('.J-ajax-board .J-board-item').each(function() {
            if ($(this).hasClass('cur')) {
                board = $(this).attr('board');
                return false;
            }
        });
        return board;
    }

    function getField() {
        var field = '';
        $('.J-ajax-table .J-ajax-a').each(function() {
            if ($(this).parent('th').hasClass('cur')) {
                field = $(this).attr('field');
                return false;
            }
        });
        return field;
    }

    function getOrder() {
        var order = '';
        $('.J-ajax-table .J-ajax-a').each(function() {
            if ($(this).parent('th').hasClass('cur')) {
                order = $(this).attr('order') ? $(this).attr('order') : 'DESC';
                return false;
            }
        });
        return order;
    }

    function getPage() {
        var page = '';
        $('.J-ajax-page a').each(function() {
            if ($(this).hasClass('click-cur')) {
                page = $(this).attr('page');
                return false;
            }
        });
        return page;
    }
    //tab页切换
    $('.J-ajax-board .J-board-item').live('click', function() {
        $(this).addClass('cur').siblings().removeClass('cur');
        var report = getReport();
        var board = getBoard();
        var field = getField();
        $('#board').attr('value', board);
        $('#field').attr('value', field);
        var href = window.location.href;
        var pageName = '';
        if (href.indexOf('gnzjl') > -1) {
            pageName = 'gnzjl';
        }
        if (href.indexOf('ggzjl') > -1) {
            pageName = 'ggzjl';
        }
        if (href.indexOf('hyzjl') > -1) {
            pageName = 'hyzjl';
        }
        switch (pageName) {
            case 'gnzjl':
            case 'ggzjl':
            case 'hyzjl':
                var param = diffRequest({
                    'date': report,
                    'board': board,
                    'ajax': 1
                });
                break;
            default:
                var param = diffRequest({
                    'date': report,
                    'board': board,
                    'field': field,
                    'ajax': 1
                });
        }
        changeContent(param, window.pageCallback);
        if (tjid == 'yjkb') {
            TA.log({ 'id': 'db_55e41085_305' });
        } else if (tjid == 'yjyg') {
            TA.log({ 'id': 'db_55ebdaaf_234' });
        } else if (tjid == 'yjgg') {
            TA.log({ 'id': 'db_55efe4c8_768' });
        } else if (tjid == 'yypl') {
            TA.log({ 'id': 'db_55f29bc3_447' });
        } else if (tjid == 'sgpx') {
            TA.log({ 'id': 'db_55f13cdd_634' });
        }
    });
    //表格排序
    $('.J-ajax-table .J-ajax-a').live('click', function() {
        if ($(this).parent('th').hasClass('cur')) {
            $(this).parent('th').find('.arr-down').toggleClass('arr-up');
            if (!$(this).attr('order')) {
                $(this).attr('order', 'ASC');
            }
        } else {
            $('.J-ajax-table th').removeClass('cur');
            $(this).parent('th').addClass('cur');
        }
        var report = getReport();
        var board = getBoard();
        var field = getField();
        var order = getOrder();
        $('#board').attr('value', board);
        $('#field').attr('value', field);
        $('#order').attr('value', order);
        var param = diffRequest({
            'date': report,
            'board': board,
            'field': field,
            'order': order,
            'ajax': 1
        });
        changeContent(param, window.pageCallback);
    });
    //表格翻页
    $('.J-ajax-page a').live('click', function() {
        $(this).addClass('click-cur').siblings().removeClass('click-cur');
        var report = getReport();
        var board = getBoard();
        var field = getField();
        var order = getOrder() == 'asc' ? 'desc' : 'asc';
        var page = getPage();
        $('#board').attr('value', board);
        $('#field').attr('value', field);
        $('#order').attr('value', order);
        $('#page').attr('value', page);
        if ($(this).parents('#J-ajax-main').attr('code')) {
            var code = $(this).parents('#J-ajax-main').attr('code');
            var param = diffRequest({
                'op': 'code',
                'code': code,
                'page': page,
                'ajax': 1
            }, 'page');

        } else {
            var param = diffRequest({
                'date': report,
                'board': board,
                'field': field,
                'order': order,
                'page': page,
                'ajax': 1
            }, 'page');
        }
        changeContent(param, window.pageCallback);
    });


    function initPage(){
        var report = getReport();
        var board = getBoard();
        var field = getField();
        var order ='desc';
        var page = getPage();

        var param = diffRequest({
            'date': report,
            'board': board,
            'field': field,
            'order': order,
            'page': page,
            'ajax': 1
        }, 'page');
        changeContent(param, window.pageCallback);
    }

    initPage();

    //下拉框
    $('.sel-report .text,.sel-report .list').click(function() {
        $(this).parents('.sel-report').find('.list').toggle();
    });
    if ($('.sel-report .list').outerHeight() > 190) {
        $('.sel-report .list').css({
            'height': 190,
            'overflow-y': 'scroll'
        })
    }
    $('.sel-report .list a').click(function() {
        var val = $(this).text();
        var textValue = $(this).parents('.sel-report').find('.text-value');
        var date = $(this).attr('date');
        textValue.text(val);
        $('#report').attr('date', date);
        $('.J-ajax-board .J-board-item').eq(0).addClass('cur').siblings().removeClass('cur');
        var param = diffRequest({ //选择报表
            'date': date,
            'ajax': 1
        });
        changeContent(param);
    }).mouseenter(function() {
        $(this).parents('.list').find('li').removeClass('cur');
        $(this).parents('li').addClass('cur');
    });
    $(document).bind('click', function(e) {
        var $clicked = $(e.target);
        if (!$clicked.parents('.sel-report').length) {
            $('.sel-report .list').hide();
        }
    });

    //搜索框
    $('.search-box .search-list a').click(function() {
        var index = $('.search-box .search-list a').index($(this));
        $(this).addClass('cur').siblings().removeClass('cur');
        $('.search-box .search-main span').eq(index).show().siblings().hide();
    });

    //锁定表头效果
    var tableThead = function() {

        if ($('#datacenter_change_content').length > 0) {
            //固定表格每个数据项的宽度，防止在表头排序时造成宽度变动的不良体验
            //$tableThead.parent().height($tableThead.parent().height());
            $('.page-table').find('.m-table thead').find('tr th').each(function(index) {
                $(this).width($(this).width());
            });
            if ($('.fixed_thead').length <= 0) {
                //创建锁定表头
                var $fixedThead = $('<div class="fixed_thead hide"><table class="m-table J-ajax-table"></table></div>');
                $fixedThead.prependTo('.container');
                //复制表头并插入到锁定表头中
                $('#datacenter_change_content').find('.page-table .m-table thead').clone().appendTo($fixedThead.find('table'));
            } else {
                var $fixedThead = $('.fixed_thead');
                //复制最新表头并替换之前表头
                $('.fixed_thead').find('table thead').html($('#datacenter_change_content').find('.page-table .m-table thead').clone().html());
            }

            try{
                //锁定表头出现的起始位置
                var fixedTheadStartPos = $('.page-table').find('.m-table thead').offset().top;
            }catch(e){
                var fixedTheadStartPos = 0;
            }
            try{
                //锁定表头出现的最后位置
                var fixedTheadEndPos = $('.m-page').offset().top;
            }catch(e){
                var fixedTheadEndPos = 0;
            }


            //屏幕滚动时锁定表头的出现和隐藏事件
            $(window).scroll(function() {
                if ($('.m-page').length <= 0) return false;
                if ($(this).scrollTop() >= fixedTheadStartPos && $(this).scrollTop() <= fixedTheadEndPos) {
                    $fixedThead.show();
                } else {
                    $fixedThead.hide();
                }
            });
        }
    };
    tableThead();

    function changeCss(stock) {
        var href = window.location.href;
        var code = stock.replace(/[^0-9]+/g, '')
        var txt, h2Txt, bkTxt;
        if (href.indexOf('yjyg') > -1) {
            txt = '业绩预告';
        } else if (href.indexOf('yjkb') > -1) {
            txt = '业绩快报';
        } else if (href.indexOf('yjgg') > -1) {
            txt = '业绩公告';
        } else if (href.indexOf('yypl') > -1) {
            txt = '业绩预披露';
        } else if (href.indexOf('sgpx') > -1) {
            txt = '送股派息';
        } else if (href.indexOf('dzjy') > -1) {
            txt = '大宗交易';
        } else if (href.indexOf('xsjj') > -1) {
            txt = '限售解禁';
        } else if (href.indexOf('ggjy') > -1) {
            txt = '高管持股';
        } else {
            return false;
        }
        h2Txt = stock + '历史' + txt;
        bkTxt = '返回' + txt;
        $('#J-ajax-main').attr('code', code);
        $('.page-main .table-tit h2').html(h2Txt);
        $('.page-main .table-tab,.page-main .table-tit .sel-report').hide();
        if ($('.backzone').length < 1) {
            $('.page-main .table-tit').append($('<div class="backzone">' + bkTxt + '</div>'));
            $('.page-nav .crumbs').find('.cur').removeClass('cur');
            $('.page-nav .crumbs').append($('<span class="gt">&gt;</span><span class="cur">' + code + '</span>'))
        } else {
            $('.page-nav .crumbs span.cur').html(code);
        }

    }
    $('.backzone').live('click', function() {
        window.location.reload();
    });

    //按键精灵个股选择及回车操作
    var clickFunc = {
        run: function(code, opt) {
            if ($('#search-center-submit').attr('action') == 'ggsd') {
                TA.log({ "id": "dbsstj", "fid": "dbdatacenter" });
                window.open('http://www.iwencai.com/search?preParams=&ts=1&f=1&qs=1&tid=pubnote&bgid=&sdate=&edate=&tid=pubnote&w=' + code);
            } else if ($('#search-center-submit').attr('action') == 'ddzz') {
                window.open('http://stockpage.10jqka.com.cn/' + code + '/');
            } else if ($('#search-center-submit').attr('action') == 'xsjjgg') {
                window.open('http://data.10jqka.com.cn/market/xsjjgg/code/' + code + '/');
            } else {
                var param = diffRequest({
                    'op': 'code',
                    'code': code,
                    'ajax': 1
                });
                var stock = $('#autocomplete_search-center .selected').html();
                changeCss(stock);
                changeContent(param);
            }
            $('#search-center').val(code);
        }
    };
    //主搜索框键盘精灵
    $("#search-center,#search-input-xx,#search-input-gp,#search-input-bk").focus(function() {
        if (this.value == this.defaultValue) {
            this.value = '';
            $(this).parents().addClass('focus');
        }
    }).blur(function() {
        if (!this.value) {
            this.value = this.defaultValue
            $(this).parents().removeClass('focus');
        }
    });
    $.fn.autocomplete && $("#search-center").autocomplete({
        stock: true,
        fund: false,
        hk: false,
        usa: false,
        extra: false,
        stype: 'new',
        clickFunc: [clickFunc]
    });
    $("#search-center-submit").click(function() {
        var code = $("#autocomplete_search-center dd[class='selected']").attr('data-code');
        if (!code) {
            code = $("#autocomplete_search-center dd:first").attr('data-code');
        }
        if ($(this).attr('action') == 'ggsd') {
            TA.log({ "id": "dbsstj", "fid": "dbdatacenter" });
            window.open('http://www.iwencai.com/search?preParams=&ts=1&f=1&qs=1&tid=pubnote&bgid=&sdate=&edate=&tid=pubnote&w=' + code);
        } else if ($('#search-center-submit').attr('action') == 'ddzz') {
            window.open('http://stockpage.10jqka.com.cn/' + code + '/');
        } else if ($(this).attr('action') == 'xsjjgg') {
            window.open('http://data.10jqka.com.cn/market/xsjjgg/code/' + code + '/');
        } else {
            var param = 'op/code/code/' + code + '/ajax/1/';
            var stock = $('#autocomplete_search-center .selected').html();
            changeCss(stock);
            changeContent(param);
        }
        $('#search-center').val(code);
    });
    //搜索信息\股票\百科
    $('#search-btn-xx,#search-btn-gp,#search-btn-bk').click(function() {
        var channel = $(this).attr('id').replace(/btn/g, "input");
        var txt = $('#' + channel).val();
        if (txt && txt != '输入股票/基金代码、简称或关键字') {
            switch (channel) {
                case 'search-input-xx':
                    window.open('http://www.iwencai.com/search?typed=1&preParams=&ts=1&f=1&qs=main_info&selfsectsn=&querytype=&searchfilter=&tid=info&w=' + txt);
                    break;
                case 'search-input-gp':
                    window.open('http://www.iwencai.com/stockpick/search?typed=1&preParams=&ts=1&f=1&qs=1&selfsectsn=&querytype=&searchfilter=&tid=stockpick&w=' + txt);
                    break;
                case 'search-input-bk':
                    window.open('http://www.iwencai.com/yike/search?typed=0&preParams=&ts=1&f=1&qs=query_recommend&selfsectsn=&querytype=&searchfilter=&tid=info&w=' + txt + '&isdetail=1')
                    break;
                default:
                    break;
            }
        }
    });
    $('#search-center-submit').on('blur', function() {
        var condition = window.getComputedStyle(document.getElementById('autocomplete_search-center'), null).display;
        if (condition == 'none') {
            $('#autocomplete_search-center').find('dl').remove();
        }
    })

    $('#search-center').on('input', function() {
        if ($(this).val() == '') {
            $('#autocomplete_search-center').find('dl').remove();
        }
    })
});