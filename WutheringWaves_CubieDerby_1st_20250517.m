clc;
% 1.今汐 2.长离 3.卡卡罗 4.守岸人 5.椿 6.小土豆 7.洛可可 8.布兰特 9.坎特蕾拉 10.赞妮 11.卡提希娅 12.菲比
%selected_players                                                        = [1,2,3,4，5，6];  
%selected_players                                                        = [7,8,9,10,11,12]; 
selected_players                                                        = [3,4,8,10]; 
loop                                                                    = 1000000;       % 模拟次数
Track_mode                                                              = 4; 
%1 随机出发顺序 随机出发位置
%2 固定出发顺序 随机出发位置（A组上半场预测款）
%3 固定出发顺序 固定出发位置（A组上半场同款）
%4 随机出发顺序 固定出发位置（A组下半场同款预测1）
%5 固定出发顺序 固定出发位置（A组下半场同款预测2）

%% 运行模拟
run_simulation(selected_players,loop,Track_mode);


function run_simulation(selected_players,loop,Track_mode)
    % 初始化结果数组
    num_selected                                                            = length(selected_players);
    winner_number                                                           = zeros(1, length(selected_players));
    sum_rank                                                                = zeros(1, length(selected_players));
    all_rank                                                                = zeros(loop, length(selected_players));
    winner_gap                                                              = zeros(1,length(selected_players));
    tic;
    for aa = 1:loop
        [winner,rank,postion_2nd,track_length]                              = simulate_race(Track_mode,selected_players);
        winner_number(find(winner == selected_players))                     = winner_number(find(winner == selected_players)) + 1;
        winner_gap(find(winner == selected_players))                        = winner_gap(find(winner == selected_players)) + (track_length - postion_2nd);
        sum_rank                                                            = sum_rank + rank;
        all_ranks(aa, :)                                                    = rank;
    end
    toc;
    % 计算排名的方差
    rank_variance = zeros(1, length(selected_players));
    for i = 1 : length(selected_players)
        rank_variance(i)                                                    = var(all_ranks(:, i));
    end
    %% 画图 (只显示参与比赛的角色)
    winner_gap_rate                                                         = winner_gap/loop;
    winner_rate                                                             = winner_number/loop;
    average_rank                                                            = sum_rank/loop;
    categories                                                              = {'今汐', '长离', '卡卡罗', '守岸人', '椿', '小土豆','洛可可','布兰特','坎特蕾拉','赞妮','卡提希娅','菲比'};
    selected_categories                                                     = categories(selected_players);
    % 创建更精致的图表
    figure('Position', [100, 100, 900, 600]); % 设置更大的图表尺寸

    % 设置左侧Y轴（夺冠率）
    yyaxis left
    hBar                                                                    = bar(winner_rate, 'FaceColor', 'flat');

    % 设置美观的颜色映射
    colormap(jet(num_selected));
    for k = 1:num_selected
        hBar.CData(k,:)                                                     = k/num_selected * [0.8 0.2 0.2] + (1-k/num_selected) * [0.2 0.2 0.8];
    end

    % 计算Y轴最大值，确保有足够空间放置数据标签
    max_winner_rate                                                         = max(winner_rate);
    y_max                                                                   = max_winner_rate * 1.15; % 增加15%的空间给数据标签

    % 添加夺冠率数据标签
    for k = 1:num_selected
        text(k, winner_rate(k) + 0.01, sprintf('%.2f%%', winner_rate(k)*100),...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontWeight', 'bold', 'Color', 'blue');
    end

    % 设置左侧Y轴属性
    ylabel('夺冠率', 'FontSize', 14, 'FontWeight', 'bold', 'Color', 'blue');
    ylim([0, y_max]);
    ax                                                                      = gca;
    ax.YColor                                                               = 'blue';

    % 设置右侧Y轴（平均排名）
    yyaxis right
    hold on;
    hLine                                                                   = plot(1:num_selected, average_rank, '-s', 'LineWidth', 2, 'MarkerSize', 8, ...
                                                                                'MarkerFaceColor', 'red', 'MarkerEdgeColor', 'red', 'Color', 'red');

    % 添加平均排名数据标签
    for k = 1:num_selected
        text(k, average_rank(k) + 0.1, sprintf('%.2f', average_rank(k)), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
            'FontWeight', 'bold', 'Color', 'red');
    end

    % 设置右侧Y轴属性
    ylabel('平均排名', 'FontSize', 14, 'FontWeight', 'bold', 'Color', 'red');
    % 设置右侧Y轴范围，注意平均排名通常是越小越好，所以可能需要倒置Y轴
    max_rank                                                                = max(average_rank) * 1.1;
    min_rank                                                                = min(min(average_rank) * 0.9, 1); % 确保最小值不小于1
    ylim([min_rank, max_rank]);
    ax                                                                      = gca;
    ax.YColor                                                               = 'red';

    % 美化坐标轴和标题
    xlabel('角色', 'FontSize', 14, 'FontWeight', 'bold');
    if Track_mode == 1
        title_str                                                           = sprintf('蒙特卡洛仿真%d次，随机出发顺序，随机出发位置', loop);
    elseif Track_mode == 2
        title_str                                                           = sprintf('蒙特卡洛仿真%d次，国服决赛上半预测，固定出发顺序，随机出发位置', loop);
    elseif Track_mode == 3
        title_str                                                           = sprintf('蒙特卡洛仿真%d次，A组上半同款后验，固定出发顺序，固定出发位置', loop);  
    elseif Track_mode == 4
        title_str                                                           = sprintf('蒙特卡洛仿真%d次，国服总决赛下半预测，随机出发顺序，固定出发位置', loop);  
    elseif Track_mode == 5
        title_str                                                           = sprintf('蒙特卡洛仿真%d次，A组下半同款预测2，固定出发顺序，固定出发位置', loop);  
    end
    title(title_str, 'FontSize', 16, 'FontWeight', 'bold');

    % 美化刻度标签
    xticks(1:num_selected);
    xticklabels(selected_categories);
    set(gca, 'FontSize', 12);
    set(gca, 'XTickLabelRotation', 0); % 可以调整为45度如果标签太长

    % 添加网格和美化图表背景
    grid on;
    set(gca, 'GridLineStyle', ':');
    set(gca, 'GridAlpha', 0.3);
    set(gca, 'Box', 'on');

    % 添加图例
    legend({'夺冠率', '平均排名'}, 'Location', 'best', 'FontSize', 12);

    % 创建排名方差和冠军领先优势图
    figure('Position', [100, 100, 900, 600]);                                  % 设置图表尺寸

    % 设置左侧Y轴（排名方差）
    yyaxis left
    hBar                                                                       = bar(rank_variance);
    set(hBar, 'FaceColor', [0.3, 0.6, 0.8]);  % 使用蓝绿色调

    % 添加方差数据标签
    for k = 1:num_selected
        text(k, rank_variance(k) + 0.1, sprintf('%.2f', rank_variance(k)),...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontWeight', 'bold', 'Color', [0.2, 0.5, 0.7]);
    end

    % 设置左侧Y轴属性
    ylabel('排名方差', 'FontSize', 14, 'FontWeight', 'bold', 'Color', [0.2, 0.5, 0.7]);
    ylim([0, max(rank_variance) * 1.15]);  % 给数据标签留出空间
    ax                                                                      = gca;
    ax.YColor                                                               = [0.2, 0.5, 0.7];

    % 设置右侧Y轴（冠军领先优势）
    yyaxis right
    hold on;
    hLine                                                                   = plot(1:num_selected, winner_gap_rate, '-d', 'LineWidth', 2, 'MarkerSize', 8, ...
                                                                            'MarkerFaceColor', [0.8, 0.4, 0.2], 'MarkerEdgeColor', [0.7, 0.3, 0.1], 'Color', [0.8, 0.4, 0.2]);

    % 添加冠军领先优势数据标签
    for k = 1:num_selected
        text(k, winner_gap_rate(k) + max(winner_gap_rate)*0.03, sprintf('%.2f', winner_gap_rate(k)), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
            'FontWeight', 'bold', 'Color', [0.7, 0.3, 0.1]);
    end

    % 设置右侧Y轴属性
    ylabel('冠军领先平均距离', 'FontSize', 14, 'FontWeight', 'bold', 'Color', [0.7, 0.3, 0.1]);
    ylim([0, max(winner_gap_rate) * 1.15]);  % 给数据标签留出空间
    ax                                                                      = gca;
    ax.YColor                                                               = [0.7, 0.3, 0.1];

    % 美化坐标轴和标题
    xlabel('角色', 'FontSize', 14, 'FontWeight', 'bold');
    title('各选手排名方差与冠军领先优势对比', 'FontSize', 16, 'FontWeight', 'bold');
    
    % 设置图表背景色
    set(gcf, 'Color', [0.97, 0.97, 0.97]);  % 浅灰色背景
    set(gca, 'Color', [0.95, 0.95, 0.95]);   % 更浅的灰色图表区域

    % 美化刻度标签
    xticks(1:num_selected);
    xticklabels(selected_categories);
    set(gca, 'FontSize', 12);
    set(gca, 'XTickLabelRotation', 0); % 可以调整为45度如果标签太长

    % 添加网格和美化图表背景
    grid on;
    set(gca, 'GridLineStyle', ':');
    set(gca, 'GridAlpha', 0.3);
    set(gca, 'Box', 'on');

    % 添加图例
    legend({'排名方差', '冠军领先优势'}, 'Location', 'best', 'FontSize', 12, 'EdgeColor', [0.7, 0.7, 0.7]);


end

function [winner,rank,postion_2nd,track_length]                             = simulate_race(Track_mode,selected_players)
    % 初始化1：今汐 2.长离 3.卡卡罗 4.守岸人 5.椿 6.小土豆
    num_players                                                             = length(selected_players);
    %比赛选手初始位置与出发顺序设置
    if Track_mode == 1
        track_length                                                        = 22; % 赛道长度
        grid                                                                = cell(1, track_length + 1); 
        grid{1}                                                             = selected_players(randperm(num_players));
        player_order                                                        = randperm(num_players); 
    elseif Track_mode == 2
        track_length                                                        = 22; 
        grid                                                                = cell(1, track_length + 1); 
        grid{1}                                                             = selected_players(randperm(num_players));
        player_order                                                        = grid{1}; 
    elseif Track_mode == 3
        track_length                                                        = 22; 
        grid                                                                = cell(1, track_length + 1); 
        grid{1}                                                             = [9,10,7,12,8,11];
        player_order                                                        = grid{1}; 
    elseif Track_mode == 4
        track_length                                                        = 25; 
        grid                                                                = cell(1, track_length + 1); 
        grid{1}                                                             = [];
        grid{2}                                                             = [10];
        grid{3}                                                             = [4,3];
        grid{4}                                                             = [8];
        player_order                                                        = selected_players(randperm(num_players));  
    elseif Track_mode == 5
        track_length                                                        = 25; 
        grid                                                                = cell(1, track_length + 1); 
        grid{2}                                                             = [10,7,9];
        grid{3}                                                             = [12];
        grid{4}                                                             = [8,11];
        player_order                                                        = [9,8,11,7,10,12];  
    end
    positions                                                               = zeros(1, length(selected_players)); % 选手当前位置
    %查找选手在grid中的序号，更新到position中
    for pos = 1:length(grid)
        if ~isempty(grid{pos})
            for p = grid{pos}
                positions(find(p == selected_players))                        = pos - 1; 
            end
        end
    end    
    %限定技区域
    cantarella                                                              = 1;
    zani_extra_steps                                                        = 0;
    cartethyia                                                              = 1;
    cartethyia_extra_steps                                                  = false;
    %runwithcantarellacube                                                   = false;
    finished                                                                = false;
    rankings                                                                = zeros(1, length(selected_players)); % 最终排名
    current_rank                                                            = 1;
    round                                                                   = 1;
    finish                                                                  = 0;
    winner                                                                  = [];
    cantarella_friends                                                      = [];
    % 游戏循环
    while ~finished
        fprintf('\n=== 第%d回合 ===\n', round);
        print_grid(grid, track_length);
        fprintf('投掷顺序为\n%s\n', strjoin(cellstr(num2str(player_order(:))), '→'));
        for i = 1:length(player_order)
            player                                                          = player_order(i);
            if positions(find(player == selected_players)) >= track_length
                continue; % 已经完成的选手不再行动
            end
            % 找到选手所在的格子
            current_pos                                                     = positions(find(player == selected_players));
            current_grid                                                    = grid{current_pos + 1}; % MATLAB索引从1开始
            idx_in_grid                                                     = find(current_grid == player, 1);
            fprintf('--- %d号选手行动 ---\n', player);
            % 检查技能
            extra_steps                                                     = 0;
            skip_others                                                     = false;
            next_turn_last                                                  = false;
            double_move                                                     = false;
            cantarella_move                                                 = false;
            cantarella_move1                                                = false;
            zani_skill                                                      = false;
            % 投掷骰子
            if player == 4
                dice                                                        = randi([2, 3]); % 4号选手骰子只有2或3
            elseif player == 10
                dice                                                        = randsample([1, 3], 1);
            else
                dice                                                        = randi([1, 3]);
            end
            fprintf('投出骰子数值: %d\n', dice); 

            % 3号选手技能
            if player == 3
                % 计算当前排名
                current_rank1                                                = currentrank(positions, selected_players, grid);
                if current_rank1(end) == player
                    extra_steps                                             = 3;
                    fprintf('3号选手触发技能：处于最后一名，本次前进额外+3格\n');
                end
            % 5号选手技能
            elseif player == 5
                if rand() <= 1
                    N                                                       = length(current_grid) - 1;
                    extra_steps                                             = N;
                    skip_others                                             = true;
                    fprintf('5号选手触发技能：额外前进%d格，左侧选手不前进\n', N);
                end
            % 7号选手技能
            elseif player == 7
                if player_order(end) == player
                    extra_steps = 2;
                    fprintf('7号选手触发技能：最后一个移动，本次前进额外+2格\n');
                end
            % 8号选手技能
            elseif player == 8
                if player_order(1) == player
                    extra_steps = 2;
                    fprintf('8号选手触发技能：第一个移动，本次前进额外+2格\n');
                end
            % 9号选手技能
            elseif player == 9
                if cantarella == 1
                    cantarella_move                                         = true;
                end
            % 10号选手技能
            elseif player == 10
                extra_steps                                                 = zani_extra_steps;
                if length(grid{current_pos + 1 }) > 1
                    if rand() <= 0.4
                        zani_skill                                          = true;
                    end
                end
                if zani_skill
                    zani_extra_steps = 2;
                    fprintf('10号选手触发技能：下回合额外+2格\n');
                else
                    zani_extra_steps = 0;
                    fprintf('10号选手未触发技能\n');
                end
            % 11号选手技能
            elseif player == 11
                if cartethyia_extra_steps
                    if rand() <= 0.6
                        extra_steps                                         = 2;
                        fprintf('11号选手触发技能：本次前进额外+2格\n');
                    else
                        fprintf('11号选手未触发技能\n');
                    end
                end
            % 12号选手技能
            elseif player == 12
                if rand() <=0.5
                    extra_steps                                             = 1;
                    fprintf('12号选手触发技能：本次前进额外+1格\n');
                end
            end
            total_steps                                                     = dice + extra_steps;
            fprintf('实际前进格数: %d\n', total_steps);
            % 6号选手技能（在骰子后触发）
            if player == 6
                if rand() <= 0.28
                    total_steps                                             = total_steps + dice;
                    fprintf('6号选手触发技能：再次前进%d格，总计前进%d格\n', dice, total_steps);
                end
            end
            % 添加到新格子
            if skip_others
                % 移动选手
                grid_old                                                        = grid{current_pos + 1 };
                new_pos                                                         = current_pos + total_steps;
                if new_pos > track_length
                    new_pos                                                     = track_length;
                end
                % 更新格子 ，从当前格子移除选手
                current_grid(current_grid == player)                            = [];
                grid{current_pos + 1}                                           = current_grid;
                % 只有自己移动
                if new_pos + 1 <= track_length + 1
                    if isempty(grid{new_pos + 1})
                        grid{new_pos + 1}                                   = [grid{new_pos + 1},player];
                    else
                        grid{new_pos + 1}                                   = [player,grid{new_pos + 1}];
                    end
                    grid{new_pos + 1}                                       = check_and_apply_player1_skill(grid{new_pos + 1},grid_old);
                end
            elseif cantarella_move
                for ii = 1 : total_steps
                    % 更新格子
                    current_pos                                             = positions(find(player == selected_players));
                    grid_old                                                = grid{current_pos + 1};
                    new_pos                                                 = current_pos + 1;
                    current_grid                                            = grid_old; 
                    idx_in_grid                                             = find(current_grid == player, 1);
                    left_players                                            = current_grid(1:idx_in_grid - 1);                    
                    if cantarella_move1
                        % 移动全部选手
                        grid{current_pos + 1}(ismember(grid{current_pos + 1}, cantarella_friends)) = [];
                        p_new_pos                                           = total_steps;
                        for p = cantarella_friends
                            p_new_pos                                       = positions(find(p == selected_players)) + 1;
                            if p_new_pos > track_length
                                p_new_pos                                   = track_length;
                            end

                            positions(find(p == selected_players))          = p_new_pos;
                        end
                        % 添加到新格子
                        if p_new_pos + 1 <= track_length + 1
                            if isempty(grid{p_new_pos + 1})
                                grid{p_new_pos + 1}                         = cantarella_friends;
                            else
                                grid{p_new_pos + 1}                         = [cantarella_friends,grid{p_new_pos + 1}];
                            end
                            grid{p_new_pos + 1}                             = check_and_apply_player1_skill(grid{p_new_pos + 1},grid_old);
                        end 
                        print_grid(grid, track_length);
                    else
                        % 移动左侧选手
                        grid{current_pos + 1}(ismember(grid{current_pos + 1}, [left_players,player])) = [];
                        p_new_pos                                           = total_steps;
                        for p = [left_players,player]
                            p_new_pos                                       = positions(find(p == selected_players)) + 1;
                            if p_new_pos > track_length
                                p_new_pos                                   = track_length;
                            end
                            positions(find(p == selected_players))          = p_new_pos;
                        end
                        % 添加到新格子
                        if p_new_pos + 1 <= track_length + 1
                            if isempty(grid{p_new_pos + 1})
                                grid{p_new_pos + 1}                  = [left_players,player];
                            else
                                grid{p_new_pos + 1}                  = [[left_players,player],grid{p_new_pos + 1}]; 
                            end
                            grid{p_new_pos + 1}                      = check_and_apply_player1_skill(grid{p_new_pos + 1},grid_old);
                        end 
                        positions(find(player == selected_players))         = p_new_pos;
                        print_grid(grid, track_length);
                        if ~isempty(setdiff(grid{p_new_pos + 1}, grid_old))
                            cantarella_move1                                = true;
                            fprintf('9号选手触发技能\n');
                            cantarella                                      = 2;
                            cantarella_friends                              = grid{p_new_pos + 1};
                        end
                    end
                end
            else
                % 移动选手
                grid_old                                                        = grid{current_pos + 1 };
                new_pos                                                         = current_pos + total_steps;
                if new_pos > track_length
                    new_pos                                                     = track_length;
                end
                % 更新格子
                % 从当前格子移除选手
                current_grid(current_grid == player)                            = [];
                grid{current_pos + 1}                                           = current_grid;
                % 左侧选手也移动
                left_players                                                = current_grid(1:idx_in_grid - 1);
                current_grid                                                = current_grid(idx_in_grid:end);
                grid{current_pos + 1}                                       = current_grid;
                
                % 移动左侧选手
                p_new_pos                                                   = total_steps;
                for p = left_players
                    p_new_pos                                               = positions(find(p == selected_players)) + total_steps;
                    if p_new_pos > track_length
                        p_new_pos                                           = track_length;
                    end
                    % 从原格子移除
                    old_pos                                                 = positions(find(p == selected_players));
                    old_grid                                                = grid{old_pos + 1};
                    old_grid(old_grid == p)                                 = [];
                    grid{old_pos + 1}                                       = old_grid;
                    positions(find(p == selected_players))                                            = p_new_pos;
                end
                % 添加到新格子
                if p_new_pos + 1 <= track_length + 1
                    if isempty(grid{new_pos + 1})
                        grid{new_pos + 1}                                   = [grid{new_pos + 1},[left_players,player]];
                    else
                        grid{new_pos + 1}                                   = [[left_players,player],grid{new_pos + 1}];
                    end
                    grid{new_pos + 1}                                       = check_and_apply_player1_skill(grid{new_pos + 1},grid_old);
                end
            end
            positions(find(player == selected_players))                     = new_pos;
            % 11号选手技能判定
            if player == 11 && cartethyia == 1
                % 计算当前排名
                current_rank1                                               = currentrank(positions, selected_players, grid);
                if current_rank1(end) == player
                        cartethyia_extra_steps                              = true;
                        cartethyia                                          = 0;
                end
            end             
            % 打印当前局面
            print_grid(grid, track_length);
            
            % 检查是否完成
            if new_pos >= track_length && isempty(winner)
                winner                                                      = player;
                rankings(player)                                            = current_rank;
                current_rank                                                = current_rank + 1;
                fprintf('%d号选手完成比赛\n', player);
                finish                                                      = 1;
                break
            end
        end
        % 计算当前排名
        current_rank1                                                       = currentrank(positions, selected_players, grid);
        
        % 2号选手技能
        next_turn_last                                                      = check_and_apply_player2_skill(grid);       
        % 更新行动顺序（2号技能）
        if next_turn_last && any(selected_players == 2)
            player_order2                                                   = selected_players(randperm(num_players));
            nonTwo                                                          = player_order2(player_order2 ~= 2);       
            twoCount                                                        = sum(player_order2 == 2);     
            player_order                                                    = [nonTwo, 2 * ones(1, twoCount)];  
        else
            player_order                                                    = selected_players(randperm(num_players));
        end   
        if finish == 1
            finished                                                        = true;
        end
        round                                                               = round + 1;
        %坎特蕾拉技能结算
        if cantarella == 2
            cantarella                                                      = 0;
        end
    end
    % 打印最终排名
    fprintf('\n=== 比赛结束 ===\n');
    fprintf('最终排名:\n');
    for i = 1:num_players
        fprintf('%d号选手: 第%d名\n', current_rank1(i), i);
    end
    winner                                                                  = current_rank1(1);
    result                                                                  = zeros(1, length(unique(current_rank1)));
    for i = 1:length(current_rank1)
        result(:, find(current_rank1(i) == selected_players))               = i; % 将排名填入相应的位置
    end
    rank                                                                    = result;
    postion_2nd                                                             = find(cellfun(@(x) any(ismember(x, current_rank1(2))), grid)) - 1;
end

function print_grid(grid, track_length)
    fprintf('当前局面:\n');
    for pos = 0:track_length
        players                                                             = grid{pos + 1};
        if ~isempty(players)
            fprintf('格子%d: [%s]\n', pos, num2str(players));
        end
    end
end
%% 1号选手技能
function grid                                                               = check_and_apply_player1_skill(grid,grid_old)
    has_one_with_left_elements                                              = false;
    if ~isequal(grid,grid_old)
        if ~isempty(grid)
            if any(grid == 1) && ~any(grid_old == 1)
                if length(grid) > 1
                    one_idx                                                 = find(grid == 1);
                    if any(one_idx > 1)
                        has_one_with_left_elements                          = true;
                        fprintf('发现1号选手左侧有选手\n');
                    end
                end
            end
        end
    end
    if has_one_with_left_elements
        if rand() <= 0.4
            fprintf('1号选手触发技能：移动到最左侧\n');
            current_grid                                                    = grid;
            current_grid(current_grid == 1)                                 = [];
            current_grid                                                    = [1, current_grid];
            grid                                                            = current_grid;
        else
            fprintf('1号选手未触发技能\n');
        end
    end
end
%% 2号选手技能
function next_turn_last                                                     = check_and_apply_player2_skill(grid) 
    has_two_with_right_elements                                             = false;
    for i = 1:length(grid)
        if ~isempty(grid{i})
            if any(grid{i} == 2)
                if length(grid{i}) > 1
                    two_idx                                                 = find(grid{i} == 2);
                    if any(two_idx < length(grid{i}))
                        has_two_with_right_elements                         = true;
                        fprintf('发现2号选手右侧有选手\n');
                        break;
                    end
                end
            end
        end
    end
    % 如果找到了满足条件的情况，触发2号选手技能
    if has_two_with_right_elements
        if rand() <= 0.65
            fprintf('2号选手触发技能：下一回合最后行动\n');
            next_turn_last                                                  = true;
        else
            fprintf('2号选手未触发技能\n');
            next_turn_last                                                  = false;
        end
    else
        next_turn_last                                                      = false;
    end 
end
%% 计算当前排名
function current_rank                                                       = currentrank(positions, selected_players, grid)
    [~, temp_rank]                                                          = sort(positions, 'descend');
    % 初始化结果
    result                                                                  = temp_rank;
    % 查找每列中是否包含selected_player
    columns_with_player                                                     = false(1, size(result, 2));
    for col = 1:size(result, 2)
        if any(selected_players(result(:, col)) == selected_players)
                columns_with_player(col)                                    = true;
        end
    end
    % 提取包含selected_player的列
    filtered_matrix                                                         = result(:, columns_with_player);
    % 如果没有找到任何包含selected_player的列，返回空矩阵并显示信息
    if isempty(filtered_matrix)
        disp(['没有找到包含 ', num2str(selected_players), ' 的列!']);
    end
    A                                                                       = selected_players(filtered_matrix);
    [unique_vals, ~, indices]                                               = unique(positions(:,columns_with_player));
    counts                                                                  = histcounts(indices, 1:max(indices)+1);
    duplicate_vals                                                          = unique_vals(counts > 1);

    for i = 1:length(duplicate_vals)
        dup_indices                                                         = find(positions(:,columns_with_player) == duplicate_vals(i));
        if length(dup_indices) > 1
            grid_values                                                     = grid{duplicate_vals(i) + 1};
            result_index                                                    = zeros(1,length(dup_indices));
            for j = 1:length(dup_indices)
                result_index(j)                                             = find(selected_players(filtered_matrix) == grid_values(j));
            end
            %B                                                               = selected_players(filtered_matrix);
            %A(result_index)                                                 = B(result_index);
            A(sort(result_index,'ascend'))                                  = grid_values;
        end
    end
    current_rank                                                            = A;
end
%垃圾桶
            %elseif runwithcantarellacube 
                % 移动选手
                %grid_old                                                    = grid{current_pos + 1 };
                %new_pos                                                     = current_pos + total_steps;
                %if new_pos > track_length
                    %new_pos                                                 = track_length;
                %end
                % 更新格子，从当前格子移除选手
                %current_grid(ismember(current_grid,cantarella_friends))            = [];
                %grid{current_pos + 1}                                       = current_grid;
                % 左侧选手也移动
                %idx_in_grid                                                 = 1;
                %left_players                                                = current_grid(1:idx_in_grid - 1);
                %current_grid                                                = current_grid(cantarella_friends(end) + 1:end);
                %grid{current_pos + 1}                                       = current_grid;
                % 移动左侧选手
                %p_new_pos                                                   = total_steps;
                %for p = [left_players,cantarella_friends]
                    %p_new_pos                                               = positions(find(p == selected_players)) + total_steps;
                    %if p_new_pos > track_length
                        %p_new_pos                                           = track_length;
                    %end
                    %positions(find(p == selected_players))                                            = p_new_pos;
                %end
                % 添加到新格子
                %if p_new_pos + 1 <= track_length + 1
                    %if isempty(grid{new_pos + 1})
                        %grid{new_pos + 1}                                   = [grid{new_pos + 1},[left_players,cantarella_friends]];
                    %else
                        %grid{new_pos + 1}                                   = [[left_players,cantarella_friends],grid{new_pos + 1}];
                    %end
                    %grid{new_pos + 1}                                       = check_and_apply_player1_skill(grid{new_pos + 1},grid_old);
                %end
                %runwithcantarellacube                                       = false;

